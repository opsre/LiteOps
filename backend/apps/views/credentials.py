import json
import uuid
import hashlib
import logging
import os
import stat
import subprocess
import tempfile
import yaml
import shutil
from datetime import datetime
from django.http import JsonResponse
from django.views import View
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.hashers import make_password, check_password # check_password 
from ..models import (
    GitlabTokenCredential,
    SSHKeyCredential,
    KubeconfigCredential,
    GitHubTokenCredential,
    User
)
from ..utils.auth import jwt_auth_required

logger = logging.getLogger('apps')

def generate_id():
    """生成唯一ID"""
    return hashlib.sha256(str(uuid.uuid4()).encode()).hexdigest()[:32]

def encrypt_sensitive_data(data, credential_type=None):
    if not data:
        return None
    if credential_type in ['gitlab_token', 'ssh_key', 'github_token']:
        return data
    return make_password(data)

CREDENTIAL_MODELS = {
    'gitlab_token': GitlabTokenCredential,
    'ssh_key': SSHKeyCredential, 
    'kubeconfig': KubeconfigCredential, 
    'github_token': GitHubTokenCredential,
}

class SSHKeyManager:
    """SSH密钥管理器 - 支持直接ssh user@host方式"""
    
    def __init__(self):
        self.ssh_dir = os.path.expanduser('~/.ssh')
        self.ensure_ssh_dir()
    
    def ensure_ssh_dir(self):
        """确保SSH目录存在并设置正确权限"""
        if not os.path.exists(self.ssh_dir):
            os.makedirs(self.ssh_dir, mode=0o700)
        else:
            os.chmod(self.ssh_dir, 0o700)
    
    def deploy_ssh_key(self, credential_id, private_key, passphrase=None):
        """部署SSH密钥到容器环境，支持直接ssh连接"""
        try:
            # 使用credential_id作为密钥文件名
            key_filename = f"id_rsa_{credential_id}"
            key_path = os.path.join(self.ssh_dir, key_filename)
            
            # 写入私钥文件
            with open(key_path, 'w') as f:
                f.write(private_key)
            
            # 设置私钥文件权限
            os.chmod(key_path, 0o600)
            
            # 如果有passphrase，发出提醒
            if passphrase:
                logger.warning(f"SSH密钥 {credential_id} 有密码保护，在CI/CD自动化环境中可能需要在脚本中通过expect等工具处理")
            
            # 创建或更新SSH配置，支持全局使用
            self.update_ssh_config_global(credential_id, key_filename)
            
            logger.info(f"SSH密钥 {credential_id} 部署成功")
            return True, "SSH密钥部署成功，现在可以直接使用 ssh user@host 进行连接"
            
        except Exception as e:
            logger.error(f"部署SSH密钥失败: {str(e)}", exc_info=True)
            return False, f"部署失败: {str(e)}"
    

    def update_ssh_config_global(self, credential_id, key_filename):
        """更新SSH配置文件，支持全局密钥使用"""
        ssh_config_file = os.path.join(self.ssh_dir, 'config')
        
        # 构建配置条目 - 使用通配符Host *，使所有连接都能使用这些密钥
        config_entry = f"""
# SSH Key Credential: {credential_id}
Host *
    IdentityFile ~/.ssh/{key_filename}
    IdentitiesOnly no
    StrictHostKeyChecking no
    UserKnownHostsFile /dev/null
    LogLevel ERROR
    # 禁用locale转发，避免远程服务器locale警告
    SendEnv -LC_*
    # CI/CD性能优化
    Compression yes
    ServerAliveInterval 60
    ServerAliveCountMax 3
    ConnectTimeout 10
    # 禁用不必要的认证方式
    GSSAPIAuthentication no

"""
        
        # 读取现有配置
        existing_config = ""
        if os.path.exists(ssh_config_file):
            with open(ssh_config_file, 'r') as f:
                existing_config = f.read()
        
        lines = existing_config.split('\n')
        new_lines = []
        skip_section = False
        
        for line in lines:
            if line.strip() == f"# SSH Key Credential: {credential_id}":
                skip_section = True
                continue
            elif skip_section and line.strip() == "":
                skip_section = False
                continue
            elif not skip_section:
                new_lines.append(line)
        
        # 添加新的配置条目到开头
        new_config = config_entry + '\n'.join(new_lines).rstrip()
        
        # 写入配置文件
        with open(ssh_config_file, 'w') as f:
            f.write(new_config)
        
        # 设置配置文件权限
        os.chmod(ssh_config_file, 0o600)
    
    def remove_ssh_key(self, credential_id):
        """移除SSH密钥和配置"""
        try:
            # 删除私钥文件
            key_filename = f"id_rsa_{credential_id}"
            key_path = os.path.join(self.ssh_dir, key_filename)
            if os.path.exists(key_path):
                os.remove(key_path)
            
            ssh_config_file = os.path.join(self.ssh_dir, 'config')
            if os.path.exists(ssh_config_file):
                with open(ssh_config_file, 'r') as f:
                    existing_config = f.read()
                
                lines = existing_config.split('\n')
                new_lines = []
                skip_section = False
                
                for line in lines:
                    if line.strip() == f"# SSH Key Credential: {credential_id}":
                        skip_section = True
                        continue
                    elif skip_section and line.strip() == "":
                        skip_section = False
                        continue
                    elif not skip_section:
                        new_lines.append(line)
                
                new_config = '\n'.join(new_lines).rstrip()
                with open(ssh_config_file, 'w') as f:
                    f.write(new_config)
            
            logger.info(f"SSH密钥 {credential_id} 清理成功")
            return True, "SSH密钥清理成功"
            
        except Exception as e:
            logger.error(f"清理SSH密钥失败: {str(e)}", exc_info=True)
            return False, f"清理失败: {str(e)}"
    
    def get_deployment_status(self, credential_id):
        """获取SSH密钥部署状态"""
        key_filename = f"id_rsa_{credential_id}"
        key_path = os.path.join(self.ssh_dir, key_filename)
        
        if os.path.exists(key_path):
            # 检查配置文件中是否有对应条目
            ssh_config_file = os.path.join(self.ssh_dir, 'config')
            if os.path.exists(ssh_config_file):
                with open(ssh_config_file, 'r') as f:
                    config_content = f.read()
                    if f"# SSH Key Credential: {credential_id}" in config_content:
                        return True, "已部署"
            return False, "配置缺失"
        return False, "未部署"


class KubeconfigManager:
    """Kubeconfig配置管理器 - 支持多集群配置合并"""
    
    def __init__(self):
        self.kube_dir = os.path.expanduser('~/.kube')
        self.config_file = os.path.join(self.kube_dir, 'config')
        self.backup_dir = os.path.join(self.kube_dir, 'backups')
        self.ensure_kube_dir()
    
    def ensure_kube_dir(self):
        """确保kubectl目录存在并设置正确权限"""
        if not os.path.exists(self.kube_dir):
            os.makedirs(self.kube_dir, mode=0o700)
        else:
            os.chmod(self.kube_dir, 0o700)
        
        # 确保备份目录存在
        if not os.path.exists(self.backup_dir):
            os.makedirs(self.backup_dir, mode=0o700)
    
    def parse_kubeconfig(self, content):
        """解析kubeconfig内容，提取集群和上下文信息"""
        try:
            config = yaml.safe_load(content)
            
            # 验证基本结构
            if not isinstance(config, dict):
                return None, "无效的kubeconfig格式：根节点必须是对象"
            
            required_keys = ['apiVersion', 'kind', 'clusters', 'users', 'contexts']
            missing_keys = [key for key in required_keys if key not in config]
            if missing_keys:
                return None, f"缺少必需的字段: {', '.join(missing_keys)}"
            
            # 提取信息
            clusters = config.get('clusters', [])
            contexts = config.get('contexts', [])
            current_context = config.get('current-context')
            
            if not clusters:
                return None, "kubeconfig中没有找到集群配置"
            
            if not contexts:
                return None, "kubeconfig中没有找到上下文配置"
            
            # 提取第一个集群和上下文的名称
            cluster_name = clusters[0].get('name', 'unknown-cluster') if clusters else 'unknown-cluster'
            context_name = current_context or (contexts[0].get('name', 'unknown-context') if contexts else 'unknown-context')
            
            return {
                'cluster_name': cluster_name,
                'context_name': context_name,
                'clusters': [c.get('name') for c in clusters],
                'contexts': [c.get('name') for c in contexts],
                'current_context': current_context
            }, None
            
        except yaml.YAMLError as e:
            return None, f"YAML格式错误: {str(e)}"
        except Exception as e:
            return None, f"解析kubeconfig失败: {str(e)}"
    
    def backup_current_config(self):
        """备份当前的kubeconfig文件"""
        if os.path.exists(self.config_file):
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_file = os.path.join(self.backup_dir, f'config_backup_{timestamp}')
            shutil.copy2(self.config_file, backup_file)
            logger.info(f"kubeconfig已备份到: {backup_file}")
            return backup_file
        return None
    
    def merge_kubeconfigs(self, credential_configs):
        """合并多个kubeconfig配置"""
        try:
            merged_config = {
                'apiVersion': 'v1',
                'kind': 'Config',
                'clusters': [],
                'users': [],
                'contexts': [],
                'current-context': None
            }
            
            all_clusters = {}
            all_users = {}
            all_contexts = {}
            first_context = None
            
            # 读取现有配置
            if os.path.exists(self.config_file):
                try:
                    with open(self.config_file, 'r') as f:
                        existing_config = yaml.safe_load(f)
                        
                    if existing_config and isinstance(existing_config, dict):
                        # 保留现有的集群、用户和上下文（非LiteOps管理的）
                        for cluster in existing_config.get('clusters', []):
                            cluster_name = cluster.get('name')
                            if cluster_name and not self._is_liteops_managed(cluster_name):
                                all_clusters[cluster_name] = cluster
                        
                        for user in existing_config.get('users', []):
                            user_name = user.get('name')
                            if user_name and not self._is_liteops_managed(user_name):
                                all_users[user_name] = user
                        
                        for context in existing_config.get('contexts', []):
                            context_name = context.get('name')
                            if context_name and not self._is_liteops_managed(context_name):
                                all_contexts[context_name] = context
                                
                        # 保留现有的current-context（不是LiteOps管理的）
                        current_context = existing_config.get('current-context')
                        if current_context and not self._is_liteops_managed(current_context):
                            merged_config['current-context'] = current_context
                            
                except Exception as e:
                    logger.warning(f"读取现有kubeconfig失败，将创建新配置: {str(e)}")
            
            # 合并新的配置
            for config_content in credential_configs:
                try:
                    config = yaml.safe_load(config_content)
                    
                    # 添加集群
                    for cluster in config.get('clusters', []):
                        cluster_name = cluster.get('name')
                        if cluster_name:
                            # 添加LiteOps标记
                            cluster_copy = cluster.copy()
                            cluster_copy['name'] = f"liteops-{cluster_name}"
                            all_clusters[cluster_copy['name']] = cluster_copy
                    
                    # 添加用户
                    for user in config.get('users', []):
                        user_name = user.get('name')
                        if user_name:
                            # 添加LiteOps标记
                            user_copy = user.copy()
                            user_copy['name'] = f"liteops-{user_name}"
                            all_users[user_copy['name']] = user_copy
                    
                    # 添加上下文
                    for context in config.get('contexts', []):
                        context_name = context.get('name')
                        if context_name and context.get('context'):
                            # 更新引用并添加LiteOps标记
                            context_copy = context.copy()
                            context_copy['name'] = f"liteops-{context_name}"
                            
                            # 更新context中的cluster和user引用
                            context_obj = context_copy['context'].copy()
                            if 'cluster' in context_obj:
                                context_obj['cluster'] = f"liteops-{context_obj['cluster']}"
                            if 'user' in context_obj:
                                context_obj['user'] = f"liteops-{context_obj['user']}"
                            context_copy['context'] = context_obj
                            
                            all_contexts[context_copy['name']] = context_copy
                            
                            # 记录第一个上下文作为默认值
                            if first_context is None:
                                first_context = context_copy['name']
                                
                except Exception as e:
                    logger.error(f"处理单个kubeconfig配置失败: {str(e)}")
                    continue
            
            # 组装最终配置
            merged_config['clusters'] = list(all_clusters.values())
            merged_config['users'] = list(all_users.values())
            merged_config['contexts'] = list(all_contexts.values())
            
            # 设置默认上下文
            if merged_config['current-context'] is None and first_context:
                merged_config['current-context'] = first_context
            
            return merged_config, None
            
        except Exception as e:
            logger.error(f"合并kubeconfig失败: {str(e)}", exc_info=True)
            return None, f"合并失败: {str(e)}"
    
    def _is_liteops_managed(self, name):
        """检查资源是否由LiteOps管理"""
        return name.startswith('liteops-')
    
    def deploy_single_kubeconfig(self, credential_id):
        """部署单个kubeconfig凭证，自动与已有凭证合并"""
        try:
            # 获取指定的kubeconfig凭证
            try:
                credential = KubeconfigCredential.objects.get(credential_id=credential_id)
            except KubeconfigCredential.DoesNotExist:
                return False, "指定的kubeconfig凭证不存在"
            
            # 获取所有已部署的kubeconfig凭证（通过检查当前config文件）
            deployed_credentials = self.get_deployed_credentials()
            
            # 添加当前要部署的凭证
            if credential_id not in deployed_credentials:
                deployed_credentials.append(credential_id)
            
            # 获取所有需要部署的凭证内容
            config_contents = []
            contexts = []
            
            for cred_id in deployed_credentials:
                try:
                    cred = KubeconfigCredential.objects.get(credential_id=cred_id)
                    config_contents.append(cred.kubeconfig_content)
                    contexts.append(f"liteops-{cred.context_name}")
                except KubeconfigCredential.DoesNotExist:
                    continue
            
            if not config_contents:
                return False, "没有有效的kubeconfig凭证可部署"
            
            # 备份当前配置
            backup_file = self.backup_current_config()
            
            # 合并配置
            merged_config, error = self.merge_kubeconfigs(config_contents)
            if error:
                return False, error
            
            # 写入合并后的配置
            with open(self.config_file, 'w') as f:
                yaml.dump(merged_config, f, default_flow_style=False, allow_unicode=True)
            
            # 设置文件权限
            os.chmod(self.config_file, 0o600)
            
            logger.info(f"Kubeconfig凭证 {credential_id} 部署成功，当前包含 {len(contexts)} 个集群上下文")
            return True, f"部署成功，当前配置包含 {len(contexts)} 个集群"
            
        except Exception as e:
            logger.error(f"部署kubeconfig凭证失败: {str(e)}", exc_info=True)
            return False, f"部署失败: {str(e)}"
    
    def get_deployed_credentials(self):
        """获取当前已部署的凭证ID列表"""
        deployed_creds = []
        
        try:
            if not os.path.exists(self.config_file):
                return deployed_creds
            
            with open(self.config_file, 'r') as f:
                config = yaml.safe_load(f)
            
            if not config or not isinstance(config, dict):
                return deployed_creds
            
            # 通过上下文名称反推凭证ID
            contexts = config.get('contexts', [])
            for context in contexts:
                context_name = context.get('name', '')
                if context_name.startswith('liteops-'):
                    # 从上下文名称中提取原始名称，然后查找对应的凭证
                    original_context = context_name[8:]  # 移除 'liteops-' 前缀
                    try:
                        cred = KubeconfigCredential.objects.get(context_name=original_context)
                        if cred.credential_id not in deployed_creds:
                            deployed_creds.append(cred.credential_id)
                    except KubeconfigCredential.DoesNotExist:
                        pass
                        
        except Exception as e:
            logger.error(f"获取已部署凭证列表失败: {str(e)}")
            
        return deployed_creds
    
    def undeploy_single_kubeconfig(self, credential_id):
        """取消部署单个kubeconfig凭证"""
        try:
            # 获取当前已部署的凭证列表
            deployed_credentials = self.get_deployed_credentials()
            
            # 移除指定的凭证
            if credential_id in deployed_credentials:
                deployed_credentials.remove(credential_id)
            
            # 备份现有配置
            backup_file = self.backup_current_config()
            
            if not deployed_credentials:
                # 如果没有其他凭证了，清理所有LiteOps配置
                return self._cleanup_liteops_config()
            else:
                # 重新部署剩余的凭证
                config_contents = []
                for cred_id in deployed_credentials:
                    try:
                        cred = KubeconfigCredential.objects.get(credential_id=cred_id)
                        config_contents.append(cred.kubeconfig_content)
                    except KubeconfigCredential.DoesNotExist:
                        continue
                
                # 合并剩余配置
                merged_config, error = self.merge_kubeconfigs(config_contents)
                if error:
                    return False, error
                
                # 写入更新后的配置
                with open(self.config_file, 'w') as f:
                    yaml.dump(merged_config, f, default_flow_style=False, allow_unicode=True)
                
                os.chmod(self.config_file, 0o600)
            
            logger.info(f"Kubeconfig凭证 {credential_id} 取消部署成功")
            return True, "取消部署成功"
            
        except Exception as e:
            logger.error(f"取消部署kubeconfig凭证失败: {str(e)}", exc_info=True)
            return False, f"取消部署失败: {str(e)}"
    
    def _cleanup_liteops_config(self):
        """清理所有LiteOps管理的配置"""
        try:
            config_file = self.config_file
            if os.path.exists(config_file):
                # 读取现有配置
                with open(config_file, 'r') as f:
                    config = yaml.safe_load(f)
                
                if config and isinstance(config, dict):
                    # 移除所有LiteOps管理的资源
                    new_config = {
                        'apiVersion': 'v1',
                        'kind': 'Config',
                        'clusters': [],
                        'users': [],
                        'contexts': [],
                        'current-context': None
                    }
                    
                    # 保留非LiteOps管理的资源
                    for cluster in config.get('clusters', []):
                        if not cluster.get('name', '').startswith('liteops-'):
                            new_config['clusters'].append(cluster)
                    
                    for user in config.get('users', []):
                        if not user.get('name', '').startswith('liteops-'):
                            new_config['users'].append(user)
                    
                    for context in config.get('contexts', []):
                        if not context.get('name', '').startswith('liteops-'):
                            new_config['contexts'].append(context)
                    
                    # 设置current-context
                    current_context = config.get('current-context')
                    if current_context and not current_context.startswith('liteops-'):
                        new_config['current-context'] = current_context
                    elif new_config['contexts']:
                        new_config['current-context'] = new_config['contexts'][0]['name']
                    
                    # 写入更新后的配置
                    with open(config_file, 'w') as f:
                        yaml.dump(new_config, f, default_flow_style=False, allow_unicode=True)
                else:
                    # 如果配置无效，删除文件
                    os.remove(config_file)
            
            return True, "清理成功"
            
        except Exception as e:
            logger.error(f"清理LiteOps配置失败: {str(e)}")
            return False, f"清理失败: {str(e)}"

    def deploy_kubeconfigs(self):
        """部署所有kubeconfig凭证到~/.kube/config"""
        try:
            # 获取所有kubeconfig凭证
            credentials = KubeconfigCredential.objects.all()
            
            if not credentials:
                return True, "没有需要部署的kubeconfig凭证"
            
            # 备份当前配置
            backup_file = self.backup_current_config()
            
            # 收集所有kubeconfig内容
            config_contents = []
            contexts = []
            
            for credential in credentials:
                config_contents.append(credential.kubeconfig_content)
                contexts.append(f"liteops-{credential.context_name}")
            
            # 合并配置
            merged_config, error = self.merge_kubeconfigs(config_contents)
            if error:
                return False, error
            
            # 写入合并后的配置
            with open(self.config_file, 'w') as f:
                yaml.dump(merged_config, f, default_flow_style=False, allow_unicode=True)
            
            # 设置文件权限
            os.chmod(self.config_file, 0o600)
            
            logger.info(f"Kubeconfig部署成功，包含 {len(contexts)} 个集群上下文")
            return True, "部署成功"
            
        except Exception as e:
            logger.error(f"部署kubeconfig失败: {str(e)}", exc_info=True)
            return False, f"部署失败: {str(e)}"

    def get_deployment_status(self, credential_id=None):
        """获取kubeconfig部署状态"""
        try:
            if not os.path.exists(self.config_file):
                return False, "未部署"
            
            # 检查是否有LiteOps管理的上下文
            with open(self.config_file, 'r') as f:
                config = yaml.safe_load(f)
            
            if not config or not isinstance(config, dict):
                return False, "配置无效"
            
            if credential_id:
                # 检查特定凭证的部署状态
                try:
                    credential = KubeconfigCredential.objects.get(credential_id=credential_id)
                    expected_context = f"liteops-{credential.context_name}"
                    
                    contexts = config.get('contexts', [])
                    for context in contexts:
                        if context.get('name') == expected_context:
                            return True, "已部署"
                    
                    return False, "未部署"
                except KubeconfigCredential.DoesNotExist:
                    return False, "凭证不存在"
            else:
                # 检查全局部署状态
                contexts = config.get('contexts', [])
                liteops_contexts = [ctx for ctx in contexts if ctx.get('name', '').startswith('liteops-')]
                
                if liteops_contexts:
                    return True, f"已部署 ({len(liteops_contexts)} 个集群)"
                else:
                    return False, "未部署"
                    
        except Exception as e:
            logger.error(f"检查kubeconfig部署状态失败: {str(e)}")
            return False, "状态未知"

@method_decorator(csrf_exempt, name='dispatch')
class CredentialView(View):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.ssh_manager = SSHKeyManager()
        self.kubeconfig_manager = KubeconfigManager()

    @method_decorator(jwt_auth_required)
    def get(self, request):
        """获取凭证列表"""
        try:
            credential_type = request.GET.get('type')
            if credential_type not in CREDENTIAL_MODELS:
                return JsonResponse({
                    'code': 400,
                    'message': '无效的凭证类型'
                })

            model = CREDENTIAL_MODELS[credential_type]
            credentials = model.objects.all()
            
            data = []
            for credential in credentials:
                item = {
                    'credential_id': credential.credential_id,
                    'name': credential.name,
                    'description': credential.description,
                    'creator': {
                        'user_id': credential.creator.user_id,
                        'name': credential.creator.name
                    },
                    'create_time': credential.create_time.strftime('%Y-%m-%d %H:%M:%S'),
                    'update_time': credential.update_time.strftime('%Y-%m-%d %H:%M:%S'),
                }

                # 根据不同凭证类型添加特定字段
                if credential_type == 'gitlab_token':
                    pass  # GitLab Token没有额外字段
                elif credential_type == 'github_token':
                    pass  # GitHub Token没有额外字段
                elif credential_type == 'ssh_key':
                    # 添加部署状态
                    deployed, status = self.ssh_manager.get_deployment_status(credential.credential_id)
                    item['deployed'] = deployed
                    item['deploy_status'] = status
                elif credential_type == 'kubeconfig':
                    # 添加集群和上下文信息
                    item['cluster_name'] = credential.cluster_name
                    item['context_name'] = credential.context_name
                    # 添加单个凭证的部署状态
                    deployed, status = self.kubeconfig_manager.get_deployment_status(credential.credential_id)
                    item['deployed'] = deployed
                    item['deploy_status'] = status

                data.append(item)

            return JsonResponse({
                'code': 200,
                'message': '获取凭证列表成功',
                'data': data
            })
        except Exception as e:
            logger.error(f'获取凭证列表失败: {str(e)}', exc_info=True)
            return JsonResponse({
                'code': 500,
                'message': f'服务器错误: {str(e)}'
            })

    @method_decorator(jwt_auth_required)
    def post(self, request):
        """创建凭证或执行部署操作"""
        try:
            data = json.loads(request.body)
            action = data.get('action', 'create')
            
            if action == 'deploy':
                return self.deploy_ssh_key(request, data)
            elif action == 'undeploy':
                return self.undeploy_ssh_key(request, data)
            elif action == 'deploy_kubeconfig':
                return self.deploy_kubeconfig(request, data)
            elif action == 'undeploy_kubeconfig':
                return self.undeploy_kubeconfig(request, data)
            else:
                return self.create_credential(request, data)
                
        except Exception as e:
            logger.error(f'处理请求失败: {str(e)}', exc_info=True)
            return JsonResponse({
                'code': 500,
                'message': f'服务器错误: {str(e)}'
            })
    
    def create_credential(self, request, data):
        """创建凭证"""
        credential_type = data.get('type')
        
        if credential_type not in CREDENTIAL_MODELS:
            return JsonResponse({
                'code': 400,
                'message': '无效的凭证类型'
            })

        # 获取当前用户
        try:
            creator = User.objects.get(user_id=request.user_id)
        except User.DoesNotExist:
            return JsonResponse({
                'code': 400,
                'message': '用户不存在'
            })

        model = CREDENTIAL_MODELS[credential_type]
        credential = model(
            credential_id=generate_id(),
            name=data.get('name'),
            description=data.get('description'),
            creator=creator
        )

        # 根据不同凭证类型设置特定字段
        if credential_type == 'gitlab_token':
            credential.token = data.get('token')  # GitLab Token 不加密
        elif credential_type == 'github_token':
            credential.token = data.get('token')  # GitHub Token 不加密
        elif credential_type == 'ssh_key':
            credential.private_key = data.get('private_key')
            credential.passphrase = data.get('passphrase')
        elif credential_type == 'kubeconfig':
            kubeconfig_content = data.get('kubeconfig_content')
            if kubeconfig_content:
                # 解析kubeconfig内容获取集群和上下文信息
                parse_result, error = self.kubeconfig_manager.parse_kubeconfig(kubeconfig_content)
                if error:
                    return JsonResponse({
                        'code': 400,
                        'message': f'Kubeconfig格式错误: {error}'
                    })
                
                credential.kubeconfig_content = kubeconfig_content
                credential.cluster_name = parse_result['cluster_name']
                credential.context_name = parse_result['context_name']

        credential.save()

        return JsonResponse({
            'code': 200,
            'message': '创建凭证成功',
            'data': {
                'credential_id': credential.credential_id
            }
        })
    
    def deploy_ssh_key(self, request, data):
        """部署SSH密钥"""
        credential_id = data.get('credential_id')
        
        if not credential_id:
            return JsonResponse({
                'code': 400,
                'message': '凭证ID不能为空'
            })
        
        try:
            credential = SSHKeyCredential.objects.get(credential_id=credential_id)
        except SSHKeyCredential.DoesNotExist:
            return JsonResponse({
                'code': 404,
                'message': 'SSH密钥凭证不存在'
            })
        
        # 执行部署
        success, message = self.ssh_manager.deploy_ssh_key(
            credential_id=credential.credential_id,
            private_key=credential.private_key,
            passphrase=credential.passphrase
        )
        
        if success:
            return JsonResponse({
                'code': 200,
                'message': message,
                'data': {
                    'credential_id': credential_id,
                    'usage_example': 'ssh root@your-server-ip',
                    'key_file': f'~/.ssh/id_rsa_{credential_id}'
                }
            })
        else:
            return JsonResponse({
                'code': 500,
                'message': message
            })
    
    def undeploy_ssh_key(self, request, data):
        """取消部署SSH密钥"""
        credential_id = data.get('credential_id')
        
        if not credential_id:
            return JsonResponse({
                'code': 400,
                'message': '凭证ID不能为空'
            })
        
        success, message = self.ssh_manager.remove_ssh_key(credential_id)
        
        if success:
            return JsonResponse({
                'code': 200,
                'message': message
            })
        else:
            return JsonResponse({
                'code': 500,
                'message': message
            })
    
    def deploy_kubeconfig(self, request, data):
        """部署单个kubeconfig凭证"""
        credential_id = data.get('credential_id')
        
        if not credential_id:
            return JsonResponse({
                'code': 400,
                'message': '凭证ID不能为空'
            })
        
        # 执行部署
        success, message = self.kubeconfig_manager.deploy_single_kubeconfig(credential_id)
        
        if success:
            return JsonResponse({
                'code': 200,
                'message': message
            })
        else:
            return JsonResponse({
                'code': 500,
                'message': message
            })
    
    def undeploy_kubeconfig(self, request, data):
        """取消部署单个kubeconfig凭证"""
        credential_id = data.get('credential_id')
        
        if not credential_id:
            return JsonResponse({
                'code': 400,
                'message': '凭证ID不能为空'
            })
        
        success, message = self.kubeconfig_manager.undeploy_single_kubeconfig(credential_id)
        
        if success:
            return JsonResponse({
                'code': 200,
                'message': message
            })
        else:
            return JsonResponse({
                'code': 500,
                'message': message
            })

    @method_decorator(jwt_auth_required)
    def put(self, request):
        """更新凭证"""
        try:
            data = json.loads(request.body)
            credential_type = data.get('type')
            credential_id = data.get('credential_id')

            if not credential_id:
                return JsonResponse({
                    'code': 400,
                    'message': '凭证ID不能为空'
                })

            if credential_type not in CREDENTIAL_MODELS:
                return JsonResponse({
                    'code': 400,
                    'message': '无效的凭证类型'
                })

            model = CREDENTIAL_MODELS[credential_type]
            try:
                credential = model.objects.get(credential_id=credential_id)
            except model.DoesNotExist:
                return JsonResponse({
                    'code': 404,
                    'message': '凭证不存在'
                })

            # 更新基本字段
            credential.name = data.get('name', credential.name)
            credential.description = data.get('description', credential.description)

            # 根据不同凭证类型更新特定字段
            if credential_type == 'gitlab_token':
                if 'token' in data:  # 只在提供新token时更新
                    credential.token = data['token']  # GitLab Token 不加密
            elif credential_type == 'github_token':
                if 'token' in data:  # 只在提供新token时更新
                    credential.token = data['token']  # GitHub Token 不加密
            elif credential_type == 'ssh_key':
                if 'private_key' in data: # 只在提供新私钥时更新
                    credential.private_key = data['private_key']
                    # 如果已部署，需要重新部署
                    deployed, _ = self.ssh_manager.get_deployment_status(credential_id)
                    if deployed:
                        self.ssh_manager.deploy_ssh_key(
                            credential_id=credential.credential_id,
                            private_key=credential.private_key,
                            passphrase=credential.passphrase
                        )
                if 'passphrase' in data: # 只在提供新密码时更新
                    credential.passphrase = data['passphrase']
            elif credential_type == 'kubeconfig':
                if 'kubeconfig_content' in data: # 只在提供新kubeconfig内容时更新
                    kubeconfig_content = data['kubeconfig_content']
                    # 解析kubeconfig内容获取集群和上下文信息
                    parse_result, error = self.kubeconfig_manager.parse_kubeconfig(kubeconfig_content)
                    if error:
                        return JsonResponse({
                            'code': 400,
                            'message': f'Kubeconfig格式错误: {error}'
                        })
                    
                    credential.kubeconfig_content = kubeconfig_content
                    credential.cluster_name = parse_result['cluster_name']
                    credential.context_name = parse_result['context_name']
                    
                    # 如果已部署，需要重新部署所有kubeconfig凭证
                    deployed, _ = self.kubeconfig_manager.get_deployment_status()
                    if deployed:
                        self.kubeconfig_manager.deploy_kubeconfigs()

            credential.save()

            return JsonResponse({
                'code': 200,
                'message': '更新凭证成功'
            })
        except Exception as e:
            logger.error(f'更新凭证失败: {str(e)}', exc_info=True)
            return JsonResponse({
                'code': 500,
                'message': f'服务器错误: {str(e)}'
            })

    @method_decorator(jwt_auth_required)
    def delete(self, request):
        """删除凭证"""
        try:
            data = json.loads(request.body)
            credential_type = data.get('type')
            credential_id = data.get('credential_id')

            if not credential_id:
                return JsonResponse({
                    'code': 400,
                    'message': '凭证ID不能为空'
                })

            if credential_type not in CREDENTIAL_MODELS:
                return JsonResponse({
                    'code': 400,
                    'message': '无效的凭证类型'
                })

            model = CREDENTIAL_MODELS[credential_type]
            try:
                credential = model.objects.get(credential_id=credential_id)
                
                # 如果是SSH密钥，先清理部署的密钥
                if credential_type == 'ssh_key':
                    self.ssh_manager.remove_ssh_key(credential_id)
                elif credential_type == 'kubeconfig':
                    # 删除kubeconfig凭证后，重新部署剩余的配置
                    credential.delete()
                    self.kubeconfig_manager.undeploy_single_kubeconfig(credential_id)
                    return JsonResponse({
                        'code': 200,
                        'message': '删除凭证成功，kubeconfig配置已更新'
                    })
                
                credential.delete()
            except model.DoesNotExist:
                return JsonResponse({
                    'code': 404,
                    'message': '凭证不存在'
                })

            return JsonResponse({
                'code': 200,
                'message': '删除凭证成功'
            })
        except Exception as e:
            logger.error(f'删除凭证失败: {str(e)}', exc_info=True)
            return JsonResponse({
                'code': 500,
                'message': f'服务器错误: {str(e)}'
            })