import os
import logging
import time
import subprocess
import tempfile
import re
import shutil
from datetime import datetime
from pathlib import Path
from django.conf import settings
from git import Repo
from git.exc import GitCommandError
from .build_stages import BuildStageExecutor
from .notifier import BuildNotifier
from .log_stream import log_stream_manager
from django.db.models import F
from ..models import BuildTask, BuildHistory
from ..views.github import get_github_token
# from ..utils.builder import Builder
# from ..utils.crypto import decrypt_sensitive_data

logger = logging.getLogger('apps')

class Builder:
    def __init__(self, task, build_number, commit_id, history):
        self.task = task
        self.build_number = build_number
        self.commit_id = commit_id
        self.history = history  # 构建历史记录
        self.log_buffer = []  # 缓存日志

        # 检查是否已有指定的版本号
        if self.history.version:
            self.version = self.history.version
            self.send_log(f"使用指定版本: {self.version}", "Version")
        else:
            # 为开发和测试环境生成新的版本号
            self.version = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{commit_id[:8]}"

        # 初始化构建时间信息
        self.build_time = {
            'start_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'stages_time': []
        }

        # 更新构建历史记录的状态和版本
        self.history.status = 'running'
        if not self.history.version:  # 只有当没有版本号时才更新
            self.history.version = self.version
        self.history.build_time = self.build_time
        self.history.save(update_fields=['status', 'version', 'build_time'])

        # 设置构建目录
        self.build_path = Path(settings.BUILD_ROOT) / task.name / self.version / task.project.name

        # 创建实时日志流
        log_stream_manager.create_build_stream(self.task.task_id, self.build_number)

    def check_if_terminated(self):
        """检查构建是否已被终止"""
        # 从数据库重新加载构建历史记录，以获取最新状态
        try:
            history_record = BuildHistory.objects.get(history_id=self.history.history_id)
            if history_record.status == 'terminated':
                # 如果状态为terminated，构建已被手动终止
                self.send_log("检测到构建已被手动终止，停止后续步骤", "System")
                return True
            return False
        except Exception as e:
            logger.error(f"检查构建状态时出错: {str(e)}", exc_info=True)
            return False

    def _filter_maven_progress(self, message):
        # 只过滤Maven下载进度信息中的Progress()部分
        if 'Progress (' in message and ('KB' in message or 'MB' in message or 'B/s' in message):
            return None

        # 过滤Maven下载进度条
        if re.match(r'^Progress \(\d+\): .+', message.strip()):
            return None

        # 过滤空的进度行
        if re.match(r'^\s*Progress\s*$', message.strip()):
            return None

        # 过滤下载进度百分比
        if re.match(r'^\s*\d+%\s*$', message.strip()):
            return None

        return message

    def send_log(self, message, stage=None, console_only=False, raw_output=False):
        """发送日志到缓存、实时流和控制台
        Args:
            message: 日志消息
            stage: 阶段名称
            console_only: 是否只输出到控制台（保留参数兼容性）
            raw_output: 是否为原始输出（不添加阶段标记）
        """
        # 过滤Maven Progress信息
        filtered_message = self._filter_maven_progress(message)
        if filtered_message is None:
            return  # 跳过被过滤的消息

        # 格式化消息
        if raw_output:
            formatted_message = filtered_message
        else:
            formatted_message = filtered_message

            # 如果有阶段名称，添加阶段标记
            if stage:
                formatted_message = f"[{stage}] {filtered_message}"

        # 缓存日志
        self.log_buffer.append(formatted_message)

        # 推送到实时日志流
        try:
            log_stream_manager.push_log(
                task_id=self.task.task_id,
                build_number=self.build_number,
                message=formatted_message + '\n',
                stage=stage
            )
        except Exception as e:
            # 降低日志级别，避免在清理阶段产生过多错误日志
            if "日志队列不存在" in str(e):
                logger.debug(f"日志队列已清理，跳过推送: {str(e)}")
            else:
                logger.error(f"推送实时日志失败: {str(e)}", exc_info=True)

        # 批量更新数据库中的构建日志
        try:
            should_update_db = (
                len(self.log_buffer) % 10 == 0 or  # 每10条日志更新一次
                not hasattr(self, '_last_db_update') or
                time.time() - getattr(self, '_last_db_update', 0) >= 5  # 每5秒更新一次
            )

            if should_update_db:
                current_log = '\n'.join(self.log_buffer)
                self.history.build_log = current_log
                self.history.save(update_fields=['build_log'])
                self._last_db_update = time.time()
        except Exception as e:
            logger.error(f"批量更新构建日志失败: {str(e)}", exc_info=True)

        # 输出到控制台 - 确保构建日志在控制台显示
        logger.info(formatted_message, extra={
            'from_builder': True,  # 添加标记以区分构建日志
            'task_id': self.task.task_id,
            'build_number': self.build_number
        })

    def _save_build_log(self):
        """保存构建日志到历史记录"""
        try:
            self.history.build_log = '\n'.join(self.log_buffer)
            self.history.save(update_fields=['build_log'])
        except Exception as e:
            logger.error(f"保存构建日志失败: {str(e)}", exc_info=True)

    def clone_repository(self):
        """克隆Git仓库"""
        try:
            # 检查构建是否已被终止
            if self.check_if_terminated():
                return False

            self.send_log("开始克隆代码...", "Git Clone")
            self.send_log(f"构建目录: {self.build_path}", "Git Clone")

            # 确保目录存在
            self.build_path.parent.mkdir(parents=True, exist_ok=True)

            # 获取Git凭证
            repository = self.task.project.repository
            self.send_log(f"仓库地址: {repository}", "Git Clone")
            
            # 根据仓库URL选择合适的Token
            git_token = None
            token_source = "未知"
            if 'github.com' in repository:
                # GitHub仓库，只使用GitHub Token
                try:
                    # 优先使用任务中配置的GitHub Token
                    task_git_token = self.task.github_token.token if self.task.github_token else None
                    token_source = "任务配置的GitHub Token" if self.task.github_token else "未配置"
                    
                    # 调用get_github_token函数获取Token，会优先使用传入的token，然后从数据库中查找
                    original_token = task_git_token
                    git_token = get_github_token(repository=repository, git_token=task_git_token)
                    # 检查token是否发生了变化，以确定token的最终来源
                    if git_token != original_token:
                        token_source = "数据库中的GitHub Token凭证"
                    self.send_log(f"获取GitHub Token成功: {'已配置' if git_token else '未配置'}", "Git Clone")
                    self.send_log(f"Token来源: {token_source}", "Git Clone")
                    # 记录token的前8位和后8位，以便识别但不泄露完整token
                    if git_token:
                        token_preview = git_token[:8] + '...' + git_token[-8:] if len(git_token) > 16 else '******'
                        self.send_log(f"Token预览: {token_preview}", "Git Clone")
                        # 检查是否是GitLab Token格式（通常以glpat-开头）
                        if git_token.startswith('glpat-'):
                            self.send_log("警告: 检测到使用了GitLab格式的Token访问GitHub仓库，这可能会导致认证失败", "Git Clone")
                except Exception as e:
                    self.send_log(f"获取GitHub Token时出错: {str(e)}", "Git Clone")
            else:
                # 其他仓库，使用GitLab Token
                git_token = self.task.git_token.token if self.task.git_token else None
                self.send_log(f"使用GitLab Token进行认证: {'已配置' if git_token else '未配置'}", "Git Clone")

            # 处理带有token的仓库URL
            if git_token and repository.startswith('http'):
                # 确保处理所有可能的URL格式
                self.send_log(f"原始仓库URL: {repository}", "Git Clone")
                
                # 移除任何现有的认证信息
                if '@' in repository:
                    # 提取域名和路径部分
                    protocol_part = repository.split('://')[0] + '://'
                    url_without_protocol = repository.split('://')[1]
                    domain_and_path = url_without_protocol.split('@')[1]
                    repository = f"{protocol_part}oauth2:{git_token}@{domain_and_path}"
                else:
                    # 标准URL格式，添加认证信息
                    repository = repository.replace('://', f'://oauth2:{git_token}@')
                
                self.send_log(f"处理后的认证URL: {repository.replace(git_token, '****')}", "Git Clone")
            else:
                if not git_token:
                    self.send_log("警告: 未配置Git Token，可能需要手动输入用户名密码", "Git Clone")

            # 使用构建历史记录中的分支
            branch = self.history.branch
            self.send_log(f"克隆分支: {branch}", "Git Clone")
            
            # 验证分支名称格式是否正确
            if not branch or not isinstance(branch, str) or len(branch.strip()) == 0:
                self.send_log("错误: 分支名称无效或为空", "Git Clone")
                return False
            
            # 验证构建路径是否有效
            if not self.build_path or not isinstance(self.build_path, Path):
                self.send_log(f"错误: 构建路径无效: {self.build_path}", "Git Clone")
                return False
            
            self.send_log("正在克隆代码，请稍候...", "Git Clone")
            self.send_log(f"克隆命令参数: repository={repository}, path={self.build_path}, branch={branch}", "Git Clone")

            # 使用自定义的git克隆方法，获取更详细的错误信息
            try:
                if not self.custom_git_clone(repository, str(self.build_path), branch):
                    return False
            except Exception as e:
                self.send_log(f"克隆代码时发生异常: {str(e)}", "Git Clone")
                return False

            # 检查构建是否已被终止
            if self.check_if_terminated():
                return False

            # 验证克隆是否成功
            if not os.path.exists(self.build_path) or not os.listdir(self.build_path):
                self.send_log("代码克隆失败：目录为空", "Git Clone")
                return False

            self.send_log("代码克隆完成", "Git Clone")
            self.send_log(f"克隆目录验证成功: {self.build_path}", "Git Clone")
            return True

        except GitCommandError as e:
            error_msg = str(e)
            self.send_log(f"克隆代码失败: {error_msg}", "Git Clone")
            
            # 分析常见的GitHub克隆失败原因
            if 'github.com' in repository:
                if '401' in error_msg or 'Unauthorized' in error_msg.lower():
                    self.send_log("错误分析: 可能是GitHub Token无效或权限不足。请检查您的Token是否已过期，以及是否有足够权限访问该仓库。", "Git Clone")
                    self.send_log("解决建议: 1. 确认Token有'repo'权限 2. 如果是组织仓库，确保Token已获得组织授权 3. 验证Token是否过期 4. 尝试使用Personal Access Token而不是Fine-grained Token", "Git Clone")
                elif '403' in error_msg or 'Forbidden' in error_msg.lower():
                    self.send_log("错误分析: 访问被拒绝。可能是Token权限不足，或者仓库设置了访问限制。", "Git Clone")
                    self.send_log("解决建议: 确认Token有足够权限，对于组织仓库可能需要额外的组织授权。", "Git Clone")
                elif '404' in error_msg or 'not found' in error_msg.lower():
                    self.send_log("错误分析: 仓库不存在或无法访问。请检查仓库URL是否正确，以及您的Token是否有访问权限。", "Git Clone")
                elif 'Could not read from remote repository' in error_msg:
                    self.send_log("错误分析: 无法从远程仓库读取数据。这通常是权限问题。", "Git Clone")
                    self.send_log("解决建议: 确认您的Token有足够的权限，并且仓库URL正确。", "Git Clone")
                
            return False
        except Exception as e:
            self.send_log(f"发生错误: {str(e)}", "Git Clone")
            return False

    def git_progress(self, op_code, cur_count, max_count=None, message=''):
        # 检查构建是否已被终止
        if self.check_if_terminated():
            self.send_log("检测到构建已被终止，停止克隆操作", "Git Clone")
            raise Exception("构建已被终止")

        # 每5秒发送一次进度信息，避免日志过多
        current_time = time.time()
        if not hasattr(self, 'last_progress_time') or current_time - self.last_progress_time >= 5:
            self.last_progress_time = current_time
            if max_count:
                progress = int(cur_count / max_count * 100)
                self.send_log(f"克隆进度: {progress}%", "Git Clone")
            elif message:
                self.send_log(f"克隆进度: {message}", "Git Clone")
        
    def custom_git_clone(self, repository, path, branch):
            """使用subprocess直接调用git命令进行克隆，获取更详细的错误信息"""
            try:
                # 构建git克隆命令
                cmd = ['git', 'clone', '-v', '--branch', branch, '--progress', repository, path]
                self.send_log(f"执行克隆命令: {' '.join(cmd)}", "Git Clone")
                
                # 开始克隆，捕获标准输出和错误输出
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                
                # 实时监控输出
                stdout_lines = []
                stderr_lines = []
                
                while True:
                    # 检查构建是否已被终止
                    if self.check_if_terminated():
                        self.send_log("检测到构建已被终止，终止克隆进程", "Git Clone")
                        process.terminate()
                        return False
                    
                    # 非阻塞读取输出
                    stdout_line = process.stdout.readline() if process.stdout else ''
                    stderr_line = process.stderr.readline() if process.stderr else ''
                    
                    # 检查进程是否结束
                    if stdout_line == '' and stderr_line == '' and process.poll() is not None:
                        break
                    
                    # 处理标准输出
                    if stdout_line:
                        stdout_lines.append(stdout_line.strip())
                        if 'Receiving objects' in stdout_line or 'Resolving deltas' in stdout_line:
                            self.send_log(f"克隆进度: {stdout_line.strip()}", "Git Clone")
                    
                    # 处理标准错误输出
                    if stderr_line:
                        stderr_lines.append(stderr_line.strip())
                        # 记录错误信息但不立即中断
                        self.send_log(f"克隆警告: {stderr_line.strip()}", "Git Clone")
                
                # 检查退出码
                exit_code = process.poll()
                if exit_code != 0:
                    # 输出完整的错误信息
                    self.send_log(f"Git克隆失败，退出码: {exit_code}", "Git Clone")
                    self.send_log(f"错误详情: {'\n'.join(stderr_lines)}", "Git Clone")
                    self.send_log(f"标准输出: {'\n'.join(stdout_lines)}", "Git Clone")
                    
                    # 分析常见的GitHub克隆失败原因
                    if 'github.com' in repository:
                        error_text = ' '.join(stderr_lines + stdout_lines).lower()
                        if '401' in error_text or 'unauthorized' in error_text:
                            self.send_log("错误分析: GitHub认证失败。可能是Token无效、过期或权限不足。", "Git Clone")
                            self.send_log("解决建议: 1. 确保使用的是GitHub Token而不是GitLab Token 2. 确认Token有'repo'权限 3. 检查Token是否过期", "Git Clone")
                        elif '403' in error_text or 'forbidden' in error_text:
                            self.send_log("错误分析: 访问被拒绝。可能是Token权限不足，或者仓库设置了访问限制。", "Git Clone")
                        elif '404' in error_text or 'not found' in error_text:
                            self.send_log("错误分析: 仓库不存在或无法访问。请检查仓库URL是否正确。", "Git Clone")
                        elif 'could not read from remote repository' in error_text:
                            self.send_log("错误分析: 无法从远程仓库读取数据。这通常是权限问题或网络问题。", "Git Clone")
                    return False
                
                self.send_log("Git克隆命令执行成功", "Git Clone")
                return True
            except Exception as e:
                self.send_log(f"执行git克隆命令时发生异常: {str(e)}", "Git Clone")
                return False

    def clone_external_scripts(self):
        """克隆外部脚本库"""
        try:
            if not self.task.use_external_script:
                return True

            # 检查外部脚本库配置
            config = self.task.external_script_config
            if not config or not config.get('repo_url') or not config.get('directory') or not config.get('branch'):
                self.send_log("外部脚本库配置不完整，跳过克隆", "External Scripts")
                return True

            # 检查构建是否已被终止
            if self.check_if_terminated():
                return False

            repo_url = config.get('repo_url')
            base_directory = config.get('directory')
            branch = config.get('branch')  # 分支为必填项
            token_id = config.get('token_id')

            # 从仓库URL中提取项目名称
            import re
            repo_name_match = re.search(r'/([^/]+?)(?:\.git)?/?$', repo_url)
            if repo_name_match:
                repo_name = repo_name_match.group(1)
                if repo_name.endswith('.git'):
                    repo_name = repo_name[:-4]
            else:
                repo_name = 'external-scripts'

            # 完整的克隆目录路径
            directory = os.path.join(base_directory, repo_name)

            self.send_log("开始克隆外部脚本库...", "External Scripts")
            self.send_log(f"仓库地址: {repo_url}", "External Scripts")
            self.send_log(f"基础目录: {base_directory}", "External Scripts")
            self.send_log(f"项目名称: {repo_name}", "External Scripts")
            self.send_log(f"完整目录: {directory}", "External Scripts")
            self.send_log(f"分支: {branch}", "External Scripts")

            # 获取Git Token（如果配置了）
            git_token = None
            if token_id:
                try:
                    # 根据仓库URL选择合适的Token类型
                    if 'github.com' in repo_url:
                        # GitHub仓库，使用GitHub Token
                        from ..models import GitHubTokenCredential
                        credential = GitHubTokenCredential.objects.get(credential_id=token_id)
                        git_token = credential.token
                        self.send_log("使用GitHub Token进行外部脚本库认证", "External Scripts")
                    else:
                        # 其他仓库，使用GitLab Token
                        from ..models import GitlabTokenCredential
                        credential = GitlabTokenCredential.objects.get(credential_id=token_id)
                        git_token = credential.token
                        self.send_log("使用GitLab Token进行外部脚本库认证", "External Scripts")
                except:
                    self.send_log("获取Git Token失败，尝试使用公开仓库方式克隆", "External Scripts")

            # 处理带有token的仓库URL
            if git_token and repo_url.startswith('http'):
                if '@' in repo_url:
                    repo_url = repo_url.split('@')[1]
                    repo_url = f'https://oauth2:{git_token}@{repo_url}'
                else:
                    repo_url = repo_url.replace('://', f'://oauth2:{git_token}@')

            # 确保基础目录存在
            os.makedirs(base_directory, exist_ok=True)

            # 如果目标目录已存在且不为空，先清空
            if os.path.exists(directory) and os.listdir(directory):
                self.send_log(f"清空现有目录: {directory}", "External Scripts")
                shutil.rmtree(directory)

            # 克隆外部脚本库
            self.send_log("正在克隆外部脚本库，请稍候...", "External Scripts")

            from git import Repo
            # 使用指定分支克隆
            Repo.clone_from(
                repo_url,
                directory,
                branch=branch
            )

            # 再次检查构建是否已被终止
            if self.check_if_terminated():
                return False

            # 验证克隆是否成功
            if not os.path.exists(directory) or not os.listdir(directory):
                self.send_log("外部脚本库克隆失败：目录为空", "External Scripts")
                return False

            self.send_log("外部脚本库克隆完成", "External Scripts")
            self.send_log(f"克隆目录验证成功: {directory}", "External Scripts")
            return True

        except Exception as e:
            self.send_log(f"克隆外部脚本库失败: {str(e)}", "External Scripts")
            # 如果用户配置了外部脚本库，克隆失败应该终止构建
            self.send_log("外部脚本库克隆失败，终止构建", "External Scripts")
            return False

    def execute_stages(self, stage_executor):
        """执行构建阶段"""
        try:
            if not self.task.stages:
                self.send_log("没有配置构建阶段", "Build Stages")
                return False

            # 检查构建是否已被终止
            if self.check_if_terminated():
                return False

            # 执行所有阶段
            success = stage_executor.execute_stages(self.task.stages, check_termination=self.check_if_terminated)
            return success

        except Exception as e:
            self.send_log(f"执行构建阶段时发生错误: {str(e)}", "Build Stages")
            return False

    def execute(self):
        """执行构建"""
        build_start_time = time.time()
        success = False # 初始化成功状态
        try:
            # 在开始构建前检查构建是否已被终止
            if self.check_if_terminated():
                self._update_build_stats(False)
                self._save_build_log()
                return False

            # 获取环境类型
            environment_type = self.task.environment.type if self.task.environment else None

            # 根据是否有分支信息决定是否需要克隆代码
            should_clone_code = (
                environment_type in ['development', 'testing'] or 
                (environment_type in ['staging', 'production'] and self.history.branch)
            )

            if should_clone_code:
                # 克隆代码
                self.send_log(f"开始克隆代码，分支: {self.history.branch}", "Git Clone")
                clone_start_time = time.time()
                if not self.clone_repository():
                    self._update_build_stats(False)  # 更新失败统计
                    self._update_build_time(build_start_time, False)
                    # 发送构建失败通知
                    notifier = BuildNotifier(self.history)
                    notifier.send_notifications()
                    return False

                # 记录代码克隆阶段的时间
                self.build_time['stages_time'].append({
                    'name': 'Git Clone',
                    'start_time': datetime.fromtimestamp(clone_start_time).strftime('%Y-%m-%d %H:%M:%S'),
                    'duration': str(int(time.time() - clone_start_time))
                })
            else:
                # 预发布/生产环境使用版本模式，不克隆代码
                # self.send_log(f"预发布/生产环境版本模式，使用版本: {self.history.version}", "Environment")
                # 创建构建目录
                os.makedirs(self.build_path, exist_ok=True)

            # 再次检查构建是否已被终止
            if self.check_if_terminated():
                self._update_build_stats(False)
                self._update_build_time(build_start_time, False)
                return False

            # 克隆外部脚本库（如果配置了）
            external_script_start_time = time.time()
            if not self.clone_external_scripts():
                self._update_build_stats(False)
                self._update_build_time(build_start_time, False)
                # 发送构建失败通知
                notifier = BuildNotifier(self.history)
                notifier.send_notifications()
                return False

            # 记录外部脚本库克隆阶段的时间（如果启用了外部脚本库）
            if self.task.use_external_script:
                self.build_time['stages_time'].append({
                    'name': 'External Scripts Clone',
                    'start_time': datetime.fromtimestamp(external_script_start_time).strftime('%Y-%m-%d %H:%M:%S'),
                    'duration': str(int(time.time() - external_script_start_time))
                })

            # 检查构建是否已被终止
            if self.check_if_terminated():
                self._update_build_stats(False)
                self._update_build_time(build_start_time, False)
                return False

            # 创建阶段执行器，传递send_log方法和构建时间记录回调
            stage_executor = BuildStageExecutor(
                str(self.build_path),
                lambda msg, stage=None, raw_output=False: self.send_log(msg, stage, raw_output=raw_output),
                self._record_stage_time
            )

            # 设置系统内置环境变量
            system_variables = {
                # 编号相关变量
                'BUILD_NUMBER': str(self.build_number),
                'VERSION': self.version,

                # Git相关变量
                'COMMIT_ID': self.commit_id,
                'BRANCH': self.history.branch,

                # 项目相关变量
                'PROJECT_NAME': self.task.project.name,
                'PROJECT_ID': self.task.project.project_id,
                'PROJECT_REPO': self.task.project.repository,

                # 任务相关变量
                'TASK_NAME': self.task.name,
                'TASK_ID': self.task.task_id,

                # 环境相关变量
                'ENVIRONMENT': self.task.environment.name,
                'ENVIRONMENT_TYPE': self.task.environment.type,
                'ENVIRONMENT_ID': self.task.environment.environment_id,

                # 别名(便于使用)
                'service_name': self.task.name,
                'build_env': self.task.environment.name,
                'branch': self.history.branch,
                'version': self.version,

                # 构建路径
                'BUILD_PATH': str(self.build_path),
                'BUILD_WORKSPACE': str(self.build_path),

                # Docker配置
                'DOCKER_BUILDKIT': '0',
                'BUILDKIT_PROGRESS': 'plain',
                
                # Locale配置 - 使用稳定的POSIX locale避免SSH连接时的警告
                'LC_ALL': 'POSIX',
                'LANG': 'POSIX',
            }

            # 添加自定义参数变量
            custom_parameters = {}
            if self.history.parameter_values:
                for param_name, selected_values in self.history.parameter_values.items():
                    custom_parameters[param_name] = ','.join(selected_values)
                    self.send_log(f"设置参数变量: {param_name}={custom_parameters[param_name]}", "Parameters")

            combined_env = {**os.environ, **system_variables, **custom_parameters}
            stage_executor.env = combined_env

            # 保存系统变量和自定义参数到文件
            all_variables = {**system_variables, **custom_parameters}
            stage_executor._save_variables_to_file(all_variables)

            # 执行构建阶段
            success = self.execute_stages(stage_executor)
            return success

        except Exception as e:
            self.send_log(f"构建过程中发生未捕获的异常: {str(e)}", "Error")
            success = False
            return False
        finally:
            # 更新构建统计和时间信息
            self._update_build_stats(success)
            self._update_build_time(build_start_time, success)

            # 确保最终日志保存到数据库
            self._save_build_log()

            # 输出构建完成状态日志
            self.history.refresh_from_db()
            final_status = self.history.status
            self.send_log(f"构建完成，状态: {final_status}", "Build")

            # 确保构建完成状态日志也保存到数据库
            self._save_build_log()

            # 通知日志流管理器构建完成
            try:
                log_stream_manager.complete_build(
                    task_id=self.task.task_id,
                    build_number=self.build_number,
                    status=final_status
                )
            except Exception as e:
                logger.error(f"通知日志流管理器构建完成失败: {str(e)}", exc_info=True)

            # 发送构建通知
            notifier = BuildNotifier(self.history)
            notifier.send_notifications()

    def _record_stage_time(self, stage_name: str, start_time: float, duration: float):
        """记录阶段执行时间
        Args:
            stage_name: 阶段名称
            start_time: 开始时间戳
            duration: 耗时（秒）
        """
        stage_time = {
            'name': stage_name,
            'start_time': datetime.fromtimestamp(start_time).strftime('%Y-%m-%d %H:%M:%S'),
            'duration': str(int(duration))
        }
        self.build_time['stages_time'].append(stage_time)

        # 更新构建历史记录的阶段信息
        self.history.stages = self.task.stages
        self.history.save(update_fields=['stages'])

    def _update_build_time(self, build_start_time: float, success: bool):
        """更新构建时间信息
        Args:
            build_start_time: 构建开始时间戳
            success: 构建是否成功
        """
        try:
            # 计算总耗时
            total_duration = int(time.time() - build_start_time)

            # 更新构建时间信息
            self.build_time['total_duration'] = str(total_duration)
            self.build_time['end_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            # 检查当前构建状态，如果已经是terminated则不覆盖状态
            self.history.refresh_from_db()
            if self.history.status != 'terminated':
                # 只有在状态不是terminated时才更新状态
                self.history.status = 'success' if success else 'failed'

            self.history.build_time = self.build_time
            self.history.save(update_fields=['status', 'build_time'])
        except Exception as e:
            logger.error(f"更新构建时间信息失败: {str(e)}", exc_info=True)

    def _update_build_stats(self, success: bool):
        """更新构建统计信息
        Args:
            success: 构建是否成功
        """
        try:
            # 检查当前构建状态，如果是terminated则不更新统计
            self.history.refresh_from_db()
            if self.history.status == 'terminated':
                return

            # 更新任务的构建统计信息
            if success:
                BuildTask.objects.filter(task_id=self.task.task_id).update(
                    success_builds=F('success_builds') + 1
                )
                # 只有成功的构建才更新版本号
                BuildTask.objects.filter(task_id=self.task.task_id).update(
                    version=self.version
                )
            else:
                BuildTask.objects.filter(task_id=self.task.task_id).update(
                    failure_builds=F('failure_builds') + 1
                )
        except Exception as e:
            logger.error(f"更新构建统计信息失败: {str(e)}", exc_info=True)

