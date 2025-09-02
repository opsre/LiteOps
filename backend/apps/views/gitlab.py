import json
import logging
import re
from .github import get_github_token, get_github_project, get_github_branches, get_github_commits
import gitlab
from django.http import JsonResponse
from django.views import View
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from ..models import Project, GitlabTokenCredential, BuildTask
from ..utils.auth import jwt_auth_required

logger = logging.getLogger('apps')

def get_gitlab_client(repository, git_token=None):
    """获取GitLab客户端"""
    try:
        if not git_token:
            # 获取第一个可用的GitLab Token凭证
            credential = GitlabTokenCredential.objects.first()
            if not credential:
                raise ValueError('未找到GitLab Token凭证')
            git_token = credential.token

        # 从仓库地址中提取GitLab实例URL
        repository_parts = repository.split('/')
        gitlab_url = '/'.join(repository_parts[:3])  # 获取到域名部分
        if not gitlab_url.startswith('http'):
            gitlab_url = f'http://{gitlab_url}'

        # 创建GitLab客户端
        gl = gitlab.Gitlab(
            url=gitlab_url,
            private_token=git_token
        )
        gl.auth()
        return gl
    except Exception as e:
        logger.error(f'获取GitLab客户端失败: {str(e)}', exc_info=True)
        raise

def get_gitlab_project(repository, git_token=None):
    """获取GitLab项目"""
    try:
        logger.info('repository=%s, git_token=%s', repository, git_token)
        
        # 根据仓库URL判断是GitHub还是GitLab
        if 'github.com' in repository:
            # 使用GitHub客户端
            return get_github_project(repository, git_token)
        else:
            # 使用GitLab客户端
            gl = get_gitlab_client(repository, git_token)
            repository_parts = repository.split('/')
            project_path = '/'.join(repository_parts[3:])  # 获取group/project部分
            project_path = project_path.replace('.git', '')
            return gl.projects.get(project_path)
    except Exception as e:
        logger.error(f'获取GitLab项目失败: {str(e)}', exc_info=True)
        raise

@method_decorator(csrf_exempt, name='dispatch')
class GitlabBranchView(View):
    @method_decorator(jwt_auth_required)
    def get(self, request):
        """获取Git分支列表"""
        try:
            task_id = request.GET.get('task_id')
            if not task_id:
                return JsonResponse({
                    'code': 400,
                    'message': '缺少任务ID'
                })

            # 获取任务信息
            try:
                task = BuildTask.objects.select_related('project', 'git_token', 'github_token').get(task_id=task_id)
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

            repository = task.project.repository
            # 根据仓库URL选择合适的Token和客户端
            if 'github.com' in repository:
                # GitHub仓库，使用GitHub Token
                token = task.github_token.token if task.github_token else None
                branch_list = get_github_branches(repository, token)
            else:
                # GitLab仓库，使用GitLab Token
                token = task.git_token.token if task.git_token else None
                gitlab_project = get_gitlab_project(repository, token)
                
                # 获取分支列表
                branches = gitlab_project.branches.list(all=True)
                branch_list = []
                for branch in branches:
                    branch_list.append({
                        'name': branch.name,
                        'protected': branch.protected,
                        'merged': branch.merged,
                        'default': branch.default,
                        'commit': {
                            'id': branch.commit['id'],
                            'title': branch.commit['title'],
                            'author_name': branch.commit['author_name'],
                            'authored_date': branch.commit['authored_date'],
                        }
                    })

            return JsonResponse({
                'code': 200,
                'message': '获取分支列表成功',
                'data': branch_list
            })
        except Exception as e:
            logger.error(f'获取分支列表失败: {str(e)}', exc_info=True)
            return JsonResponse({
                'code': 500,
                'message': f'服务器错误: {str(e)}'
            })

@method_decorator(csrf_exempt, name='dispatch')
class GitlabCommitView(View):
    @method_decorator(jwt_auth_required)
    def get(self, request):
        """获取Git提交记录"""
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
                task = BuildTask.objects.select_related('project', 'git_token', 'github_token').get(task_id=task_id)
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

            repository = task.project.repository
            # 根据仓库URL选择合适的Token和客户端
            if 'github.com' in repository:
                # GitHub仓库，使用GitHub Token
                token = task.github_token.token if task.github_token else None
                commit_list = get_github_commits(repository, branch, token)
            else:
                # GitLab仓库，使用GitLab Token
                token = task.git_token.token if task.git_token else None
                gitlab_project = get_gitlab_project(repository, token)
                
                # 获取最近的提交记录
                commits = gitlab_project.commits.list(
                    ref_name=branch,
                    all=False,
                    per_page=20,  # 增加返回数量
                    order_by='created_at'
                )

                commit_list = []
                for commit in commits:
                    commit_list.append({
                        'id': commit.id,
                        'short_id': commit.short_id,
                        'title': commit.title,
                        'message': commit.message,
                        'author_name': commit.author_name,
                        'author_email': commit.author_email,
                        'authored_date': commit.authored_date,
                        'created_at': commit.created_at,
                        'web_url': commit.web_url
                    })

            return JsonResponse({
                'code': 200,
                'message': '获取提交记录成功',
                'data': commit_list
            })
        except Exception as e:
            logger.error(f'获取提交记录失败: {str(e)}', exc_info=True)
            return JsonResponse({
                'code': 500,
                'message': f'服务器错误: {str(e)}'
            })