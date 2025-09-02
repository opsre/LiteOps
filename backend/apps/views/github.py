import json
import logging
import requests
from django.http import JsonResponse
from django.views import View
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from ..models import Project, BuildTask, GitHubTokenCredential
from ..utils.auth import jwt_auth_required

logger = logging.getLogger('apps')

def get_github_token(repository=None, git_token=None):
    """获取GitHub Token"""
    try:
        if git_token:
            return git_token
        
        # 获取第一个可用的GitHub Token凭证
        credential = GitHubTokenCredential.objects.first()
        if not credential:
            raise ValueError('未找到GitHub Token凭证')
        return credential.token
    except Exception as e:
        logger.error(f'获取GitHub Token失败: {str(e)}', exc_info=True)
        raise

def parse_github_repository(repository):
    """解析GitHub仓库URL，提取owner和repo名称"""
    try:
        # 支持的URL格式：
        # 1. https://github.com/owner/repo.git
        # 2. https://github.com/owner/repo
        # 3. git@github.com:owner/repo.git
        # 4. owner/repo (简短格式)
        
        if repository.endswith('.git'):
            repository = repository[:-4]
            
        if '/' not in repository:
            raise ValueError(f'无效的GitHub仓库地址: {repository}，必须包含斜杠分隔的owner和repo名称')
            
        if repository.startswith('git@github.com:'):
            # git@github.com:owner/repo 格式
            parts = repository.split(':')
            path_parts = parts[1].split('/')
            owner = path_parts[0]
            repo = path_parts[1]
        elif repository.startswith('https://github.com/'):
            # https://github.com/owner/repo 格式
            parts = repository.split('/')
            if len(parts) < 5:
                raise ValueError(f'无效的GitHub仓库地址: {repository}，格式应为 https://github.com/owner/repo')
            owner = parts[3]
            repo = parts[4]
        elif repository.startswith('http://github.com/'):
            # http://github.com/owner/repo 格式
            parts = repository.split('/')
            if len(parts) < 5:
                raise ValueError(f'无效的GitHub仓库地址: {repository}，格式应为 http://github.com/owner/repo')
            owner = parts[3]
            repo = parts[4]
        else:
            # owner/repo 简短格式
            parts = repository.split('/')
            if len(parts) < 2:
                raise ValueError(f'无效的GitHub仓库地址: {repository}，格式应为 owner/repo')
            owner = parts[0]
            repo = '/'.join(parts[1:])  # 支持repo中可能包含的斜杠（如仓库路径中有子目录）
            
        return owner, repo
    except Exception as e:
        logger.error(f'解析GitHub仓库地址失败: {str(e)}', exc_info=True)
        raise

def get_github_project(repository, token=None):
    """获取GitHub项目信息"""
    try:
        owner, repo = parse_github_repository(repository)
        token = get_github_token(repository, token)
        
        url = f'https://api.github.com/repos/{owner}/{repo}'
        headers = {
            'Authorization': f'token {token}',
            'Accept': 'application/vnd.github.v3+json'
        }
        
        logger.info(f'请求GitHub项目信息: url={url}, owner={owner}, repo={repo}')
        response = requests.get(url, headers=headers)
        
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            if response.status_code == 404:
                # 404错误表示仓库不存在或没有访问权限
                logger.error(f'GitHub仓库不存在或无访问权限: {owner}/{repo}, 错误: {str(e)}')
                raise ValueError(f'GitHub仓库 {owner}/{repo} 不存在，或者您的令牌没有访问权限。如果是组织仓库，请确认令牌已获得组织授权。')
            elif response.status_code == 401:
                # 401错误表示令牌无效或过期
                logger.error(f'GitHub令牌无效或过期: {str(e)}')
                raise ValueError('GitHub令牌无效或已过期，请检查您的令牌配置')
            elif response.status_code == 403:
                # 403错误表示令牌没有足够权限
                logger.error(f'GitHub令牌权限不足: {str(e)}')
                raise ValueError('GitHub令牌权限不足，请确保令牌具有足够的权限访问该仓库。对于组织仓库，请确认令牌已获得组织授权。')
            else:
                # 其他HTTP错误
                logger.error(f'获取GitHub项目信息失败: {str(e)}')
                raise
        
        project_data = response.json()
        
        # 创建一个模拟对象，具有与GitLab项目类似的接口
        class MockGitHubProject:
            def __init__(self, data):
                self.data = data
                
            def branches(self):
                # 这个方法不需要实现，因为我们在get_github_branches中直接使用API
                pass
                
            def commits(self):
                # 这个方法不需要实现，因为我们在get_github_commits中直接使用API
                pass
        
        return MockGitHubProject(project_data)
    except Exception as e:
        logger.error(f'获取GitHub项目失败: {str(e)}', exc_info=True)
        raise

def get_github_branches(repository, token=None):
    """获取GitHub仓库的分支列表"""
    try:
        owner, repo = parse_github_repository(repository)
        token = get_github_token(repository, token)
        
        url = f'https://api.github.com/repos/{owner}/{repo}/branches'
        headers = {
            'Authorization': f'token {token}',
            'Accept': 'application/vnd.github.v3+json'
        }
        
        logger.info(f'请求GitHub分支列表: url={url}, owner={owner}, repo={repo}')
        response = requests.get(url, headers=headers)
        
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            if response.status_code == 404:
                # 404错误可能的原因：仓库不存在、没有访问权限或令牌无效
                logger.error(f'GitHub仓库不存在或无访问权限: {owner}/{repo}, 错误: {str(e)}')
                # 区分个人仓库和组织仓库的错误信息
                if '/' in owner:  # 简单判断是否为嵌套组织路径
                    raise ValueError(f'GitHub组织仓库 {owner}/{repo} 不存在，或者您的令牌没有访问权限。请确认令牌已获得组织授权。')
                else:
                    raise ValueError(f'GitHub仓库 {owner}/{repo} 不存在，或者您的令牌没有访问权限。如果是组织仓库，请确认令牌已获得组织授权。')
            elif response.status_code == 401:
                # 401错误表示令牌无效或过期
                logger.error(f'GitHub令牌无效或过期: {str(e)}')
                raise ValueError('GitHub令牌无效或已过期，请检查您的令牌配置')
            elif response.status_code == 403:
                # 403错误表示令牌没有足够权限
                logger.error(f'GitHub令牌权限不足: {str(e)}')
                raise ValueError('GitHub令牌权限不足，请确保令牌具有足够的权限访问该仓库。对于组织仓库，请确认令牌已获得组织授权。')
            else:
                # 其他HTTP错误
                logger.error(f'获取GitHub分支列表失败: {str(e)}')
                raise
        
        branches = response.json()
        
        # 转换为与GitLab视图相同的返回格式
        branch_list = []
        for branch in branches:
            # 获取分支的默认状态（GitHub API不直接提供，这里假设master或main是默认分支）
            is_default = branch['name'] in ['master', 'main']
            
            # 获取分支的提交信息
            commit_info = branch['commit']
            
            branch_list.append({
                'name': branch['name'],
                'protected': False,  # GitHub API不直接提供此信息，默认为False
                'merged': False,     # GitHub API不直接提供此信息，默认为False
                'default': is_default,
                'commit': {
                    'id': commit_info['sha'],
                    'title': 'No commit message available',
                    'author_name': 'Unknown',
                    'authored_date': '',
                }
            })
        
        return branch_list
    except Exception as e:
        logger.error(f'获取GitHub分支列表失败: {str(e)}', exc_info=True)
        raise

def get_github_commits(repository, branch, token=None):
    """获取GitHub仓库指定分支的提交记录"""
    try:
        owner, repo = parse_github_repository(repository)
        token = get_github_token(repository, token)
        
        url = f'https://api.github.com/repos/{owner}/{repo}/commits'
        headers = {
            'Authorization': f'token {token}',
            'Accept': 'application/vnd.github.v3+json'
        }
        params = {
            'sha': branch,
            'per_page': 20  # 获取最近的20条提交记录
        }
        
        logger.info(f'请求GitHub提交记录: url={url}, owner={owner}, repo={repo}, branch={branch}')
        response = requests.get(url, headers=headers, params=params)
        
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            if response.status_code == 404:
                # 404错误可能的原因：仓库不存在、分支不存在、没有访问权限或令牌无效
                logger.error(f'GitHub仓库不存在、分支不存在或无访问权限: {owner}/{repo}, 分支: {branch}, 错误: {str(e)}')
                # 区分个人仓库和组织仓库的错误信息
                if '/' in owner:  # 简单判断是否为嵌套组织路径
                    raise ValueError(f'GitHub组织仓库 {owner}/{repo} 或分支 {branch} 不存在，或者您的令牌没有访问权限。请确认令牌已获得组织授权。')
                else:
                    raise ValueError(f'GitHub仓库 {owner}/{repo} 或分支 {branch} 不存在，或者您的令牌没有访问权限。如果是组织仓库，请确认令牌已获得组织授权。')
            elif response.status_code == 401:
                # 401错误表示令牌无效或过期
                logger.error(f'GitHub令牌无效或过期: {str(e)}')
                raise ValueError('GitHub令牌无效或已过期，请检查您的令牌配置')
            elif response.status_code == 403:
                # 403错误表示令牌没有足够权限
                logger.error(f'GitHub令牌权限不足: {str(e)}')
                raise ValueError('GitHub令牌权限不足，请确保令牌具有足够的权限访问该仓库。对于组织仓库，请确认令牌已获得组织授权。')
            else:
                # 其他HTTP错误
                logger.error(f'获取GitHub提交记录失败: {str(e)}')
                raise
        
        commits = response.json()
        
        # 转换为与GitLab视图相同的返回格式
        commit_list = []
        for commit in commits:
            commit_list.append({
                'id': commit['sha'],
                'short_id': commit['sha'][:8],
                'title': commit['commit']['message'].split('\n')[0],
                'message': commit['commit']['message'],
                'author_name': commit['commit']['author']['name'],
                'author_email': commit['commit']['author']['email'],
                'authored_date': commit['commit']['author']['date'],
                'created_at': commit['commit']['committer']['date'],
                'web_url': commit['html_url']
            })
        
        return commit_list
    except Exception as e:
        logger.error(f'获取GitHub提交记录失败: {str(e)}', exc_info=True)
        raise

@method_decorator(csrf_exempt, name='dispatch')
class GithubBranchView(View):
    @method_decorator(jwt_auth_required)
    def get(self, request):
        """获取GitHub分支列表"""
        try:
            task_id = request.GET.get('task_id')
            if not task_id:
                return JsonResponse({
                    'code': 400,
                    'message': '缺少任务ID'
                })

            # 获取任务信息
            try:
                task = BuildTask.objects.select_related('project', 'github_token').get(task_id=task_id)
            except BuildTask.DoesNotExist:
                return JsonResponse({
                    'code': 404,
                    'message': '任务不存在'
                })

            if not task.project or not task.project.repository:
                return JsonResponse({
                    'code': 400,
                    'message': '任务未配置Git仓库'
                })

            # 获取GitHub分支列表
            token = task.github_token.token if task.github_token else None
            branch_list = get_github_branches(
                task.project.repository,
                token
            )

            return JsonResponse({
                'code': 200,
                'message': '获取分支列表成功',
                'data': branch_list
            })
        except Exception as e:
            logger.error(f'获取GitHub分支列表失败: {str(e)}', exc_info=True)
            return JsonResponse({
                'code': 500,
                'message': f'服务器错误: {str(e)}'
            })

@method_decorator(csrf_exempt, name='dispatch')
class GithubCommitView(View):
    @method_decorator(jwt_auth_required)
    def get(self, request):
        """获取GitHub提交记录"""
        try:
            task_id = request.GET.get('task_id')
            branch = request.GET.get('branch')

            if not all([task_id, branch]):
                return JsonResponse({
                    'code': 400,
                    'message': '缺少必要参数'
                })

            # 获取任务信息
            try:
                task = BuildTask.objects.select_related('project', 'github_token').get(task_id=task_id)
            except BuildTask.DoesNotExist:
                return JsonResponse({
                    'code': 404,
                    'message': '任务不存在'
                })

            if not task.project or not task.project.repository:
                return JsonResponse({
                    'code': 400,
                    'message': '任务未配置Git仓库'
                })

            # 获取GitHub提交记录
            token = task.github_token.token if task.github_token else None
            commit_list = get_github_commits(
                task.project.repository,
                branch,
                token
            )

            return JsonResponse({
                'code': 200,
                'message': '获取提交记录成功',
                'data': commit_list
            })
        except Exception as e:
            logger.error(f'获取GitHub提交记录失败: {str(e)}', exc_info=True)
            return JsonResponse({
                'code': 500,
                'message': f'服务器错误: {str(e)}'
            })