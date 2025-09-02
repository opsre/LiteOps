import json
import logging
from django.http import JsonResponse
from django.views import View
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from ..models import BuildTask, BuildHistory, User
from ..utils.builder import Builder
import threading

logger = logging.getLogger('apps')

@method_decorator(csrf_exempt, name='dispatch')
class GitHubWebhookView(View):
    """GitHub Webhook处理视图"""
    
    def post(self, request, task_id):
        """处理GitHub Push Events"""
        try:
            # 验证token
            token = request.GET.get('token')
            if not token:
                logger.warning(f"Webhook请求缺少token: task_id={task_id}")
                return JsonResponse({
                    'error': 'Missing token'
                }, status=401)

            # 查找对应的构建任务
            try:
                task = BuildTask.objects.get(task_id=task_id, webhook_token=token)
            except BuildTask.DoesNotExist:
                logger.warning(f"Webhook token验证失败: task_id={task_id}, token={token}")
                return JsonResponse({
                    'error': 'Invalid task or token'
                }, status=404)

            # 检查任务是否启用自动构建
            if not task.auto_build_enabled:
                logger.info(f"任务[{task_id}]未启用自动构建，忽略webhook")
                return JsonResponse({
                    'message': 'Auto build is not enabled for this task'
                })

            # 检查任务状态
            if task.status == 'disabled':
                logger.info(f"任务[{task_id}]已禁用，忽略webhook")
                return JsonResponse({
                    'message': 'Task is disabled'
                })

            # 是否有正在进行的构建
            if task.building_status == 'building':
                logger.info(f"任务[{task_id}]正在构建中，忽略webhook")
                return JsonResponse({
                    'message': 'Build is already in progress'
                })

            # 解析webhook数据
            try:
                webhook_data = json.loads(request.body)
            except json.JSONDecodeError:
                logger.error(f"Webhook数据解析失败: task_id={task_id}")
                return JsonResponse({
                    'error': 'Invalid JSON data'
                }, status=400)

            # 是否是push事件
            event_name = request.headers.get('X-GitHub-Event', '')
            if event_name != 'push':
                logger.info(f"忽略非Push事件: {event_name}, task_id={task_id}")
                return JsonResponse({
                    'message': f'Ignored event: {event_name}'
                })

            # 提取分支信息
            ref = webhook_data.get('ref', '')
            if not ref.startswith('refs/heads/'):
                logger.info(f"忽略非分支推送: {ref}, task_id={task_id}")
                return JsonResponse({
                    'message': f'Ignored non-branch push: {ref}'
                })

            branch = ref.replace('refs/heads/', '')
            
            # 检查分支是否在自动构建配置中
            if not is_branch_matched(branch, task.auto_build_branches):
                logger.info(f"分支[{branch}]不在自动构建配置中，忽略webhook: task_id={task_id}")
                return JsonResponse({
                    'message': f'Branch {branch} is not configured for auto build'
                })

            # 提取提交信息
            head_commit = webhook_data.get('head_commit', {})
            if not head_commit:
                logger.warning(f"Webhook数据中没有提交信息: task_id={task_id}")
                return JsonResponse({
                    'error': 'No commits found in webhook data'
                }, status=400)

            commit_id = head_commit.get('id', '')
            commit_message = head_commit.get('message', '').strip()
            commit_author = head_commit.get('author', {}).get('name', 'Unknown')

            if not commit_id:
                logger.error(f"提交ID为空: task_id={task_id}")
                return JsonResponse({
                    'error': 'Commit ID is empty'
                }, status=400)

            env_type = task.environment.type if task.environment else None
            if env_type not in ['development', 'testing']:
                logger.warning(f"环境类型[{env_type}]不支持自动构建: task_id={task_id}")
                return JsonResponse({
                    'message': f'Environment type {env_type} does not support auto build'
                })

            logger.info(f"触发自动构建: task_id={task_id}, branch={branch}, commit={commit_id[:8]}, author={commit_author}")

            # 在新线程中执行自动构建
            build_thread = threading.Thread(
                target=execute_auto_build,
                args=(task, branch, commit_id, commit_message, commit_author)
            )
            build_thread.start()

            return JsonResponse({
                'message': 'Auto build triggered successfully',
                'task_id': task_id,
                'branch': branch,
                'commit_id': commit_id[:8],
                'commit_message': commit_message[:100]
            })

        except Exception as e:
            logger.error(f"Webhook处理失败: {str(e)}", exc_info=True)
            return JsonResponse({
                'error': f'Internal server error: {str(e)}'
            }, status=500)

    def get(self, request, task_id):
        """用于测试webhook配置"""
        try:
            token = request.GET.get('token')
            if not token:
                return JsonResponse({
                    'error': 'Missing token'
                }, status=401)

            try:
                task = BuildTask.objects.get(task_id=task_id, webhook_token=token)
            except BuildTask.DoesNotExist:
                return JsonResponse({
                    'error': 'Invalid task or token'
                }, status=404)

            return JsonResponse({
                'message': 'Webhook configuration is valid',
                'task_name': task.name,
                'auto_build_enabled': task.auto_build_enabled,
                'auto_build_branches': task.auto_build_branches
            })

        except Exception as e:
            logger.error(f"Webhook测试失败: {str(e)}", exc_info=True)
            return JsonResponse({
                'error': f'Internal server error: {str(e)}'
            }, status=500)

def execute_auto_build(task, branch, commit_id, commit_message, commit_author):
    """执行自动构建任务"""
    try:
        # 生成构建号
        from django.db.models import F
        from ..views.build import generate_id
        
        # 更新任务构建号并获取新的构建号
        task.last_build_number = F('last_build_number') + 1
        task.total_builds = F('total_builds') + 1
        task.building_status = 'building'
        task.save()
        
        # 重新获取任务以获取更新后的构建号
        task.refresh_from_db()
        build_number = task.last_build_number

        # 创建构建历史记录
        history = BuildHistory.objects.create(
            history_id=generate_id(),
            task=task,
            build_number=build_number,
            branch=branch,
            commit_id=commit_id,
            status='pending',
            requirement=f"自动构建: {commit_message[:200]} (by {commit_author})",  # 使用提交信息作为构建需求
            parameter_values=get_default_parameter_values(task.parameters),  # 使用默认参数值
            operator=None  # 自动构建没有操作人
        )

        builder = Builder(task, build_number, commit_id, history)
        builder.execute()
        
    except Exception as e:
        logger.error(f"自动构建执行失败: {str(e)}", exc_info=True)
    finally:
        # 无论构建成功、失败或异常，都将构建状态重置为空闲
        from django.db import transaction
        with transaction.atomic():
            BuildTask.objects.filter(task_id=task.task_id).update(building_status='idle')
            logger.info(f"任务 [{task.task_id}] 自动构建状态已重置为空闲")

def get_default_parameter_values(parameters):
    """获取参数的默认值"""
    if not parameters:
        return {}
    
    default_values = {}
    for param in parameters:
        param_name = param.get('name')
        default_list = param.get('default_values', [])
        if param_name and default_list:
            default_values[param_name] = default_list
    
    return default_values

def is_branch_matched(branch_name, branch_list):
    """检查分支是否在配置的分支列表中"""
    return branch_name in branch_list

@method_decorator(csrf_exempt, name='dispatch')
class GitLabWebhookView(View):
    """GitLab Webhook处理视图"""
    
    def post(self, request, task_id):
        """处理GitLab Push Events"""
        try:
            # 验证token
            token = request.GET.get('token')
            if not token:
                logger.warning(f"Webhook请求缺少token: task_id={task_id}")
                return JsonResponse({
                    'error': 'Missing token'
                }, status=401)

            # 查找对应的构建任务
            try:
                task = BuildTask.objects.get(task_id=task_id, webhook_token=token)
            except BuildTask.DoesNotExist:
                logger.warning(f"Webhook token验证失败: task_id={task_id}, token={token}")
                return JsonResponse({
                    'error': 'Invalid task or token'
                }, status=404)

            # 检查任务是否启用自动构建
            if not task.auto_build_enabled:
                logger.info(f"任务[{task_id}]未启用自动构建，忽略webhook")
                return JsonResponse({
                    'message': 'Auto build is not enabled for this task'
                })

            # 检查任务状态
            if task.status == 'disabled':
                logger.info(f"任务[{task_id}]已禁用，忽略webhook")
                return JsonResponse({
                    'message': 'Task is disabled'
                })

            # 是否有正在进行的构建
            if task.building_status == 'building':
                logger.info(f"任务[{task_id}]正在构建中，忽略webhook")
                return JsonResponse({
                    'message': 'Build is already in progress'
                })

            # 解析webhook数据
            try:
                webhook_data = json.loads(request.body)
            except json.JSONDecodeError:
                logger.error(f"Webhook数据解析失败: task_id={task_id}")
                return JsonResponse({
                    'error': 'Invalid JSON data'
                }, status=400)

            # 是否是push事件
            event_name = request.headers.get('X-Gitlab-Event', '')
            if event_name != 'Push Hook':
                logger.info(f"忽略非Push事件: {event_name}, task_id={task_id}")
                return JsonResponse({
                    'message': f'Ignored event: {event_name}'
                })

            # 提取分支信息
            ref = webhook_data.get('ref', '')
            if not ref.startswith('refs/heads/'):
                logger.info(f"忽略非分支推送: {ref}, task_id={task_id}")
                return JsonResponse({
                    'message': f'Ignored non-branch push: {ref}'
                })

            branch = ref.replace('refs/heads/', '')
            
            # 检查分支是否在自动构建配置中
            if not is_branch_matched(branch, task.auto_build_branches):
                logger.info(f"分支[{branch}]不在自动构建配置中，忽略webhook: task_id={task_id}")
                return JsonResponse({
                    'message': f'Branch {branch} is not configured for auto build'
                })

            # 提取提交信息
            commits = webhook_data.get('commits', [])
            if not commits:
                logger.warning(f"Webhook数据中没有提交信息: task_id={task_id}")
                return JsonResponse({
                    'error': 'No commits found in webhook data'
                }, status=400)

            # 使用最新的提交
            latest_commit = commits[-1]
            commit_id = latest_commit.get('id', '')
            commit_message = latest_commit.get('message', '').strip()
            commit_author = latest_commit.get('author', {}).get('name', 'Unknown')

            if not commit_id:
                logger.error(f"提交ID为空: task_id={task_id}")
                return JsonResponse({
                    'error': 'Commit ID is empty'
                }, status=400)

            env_type = task.environment.type if task.environment else None
            if env_type not in ['development', 'testing']:
                logger.warning(f"环境类型[{env_type}]不支持自动构建: task_id={task_id}")
                return JsonResponse({
                    'message': f'Environment type {env_type} does not support auto build'
                })

            logger.info(f"触发自动构建: task_id={task_id}, branch={branch}, commit={commit_id[:8]}, author={commit_author}")

            # 在新线程中执行自动构建
            build_thread = threading.Thread(
                target=execute_auto_build,
                args=(task, branch, commit_id, commit_message, commit_author)
            )
            build_thread.start()

            return JsonResponse({
                'message': 'Auto build triggered successfully',
                'task_id': task_id,
                'branch': branch,
                'commit_id': commit_id[:8],
                'commit_message': commit_message[:100]
            })

        except Exception as e:
            logger.error(f"Webhook处理失败: {str(e)}", exc_info=True)
            return JsonResponse({
                'error': f'Internal server error: {str(e)}'
            }, status=500)

    def get(self, request, task_id):
        """用于测试webhook配置"""
        try:
            token = request.GET.get('token')
            if not token:
                return JsonResponse({
                    'error': 'Missing token'
                }, status=401)

            try:
                task = BuildTask.objects.get(task_id=task_id, webhook_token=token)
            except BuildTask.DoesNotExist:
                return JsonResponse({
                    'error': 'Invalid task or token'
                }, status=404)

            return JsonResponse({
                'message': 'Webhook configuration is valid',
                'task_name': task.name,
                'auto_build_enabled': task.auto_build_enabled,
                'auto_build_branches': task.auto_build_branches
            })

        except Exception as e:
            logger.error(f"Webhook测试失败: {str(e)}", exc_info=True)
            return JsonResponse({
                'error': f'Internal server error: {str(e)}'
            }, status=500)