import json
import uuid
import hashlib
import logging
import threading
import time
from datetime import datetime

from django.http import JsonResponse
from django.views import View
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction
from django.db.models import Q, F
from ..models import BuildTask, BuildHistory, Project, Environment, GitlabTokenCredential, User, NotificationRobot
from ..utils.auth import jwt_auth_required
from ..utils.builder import Builder
from ..utils.permissions import get_user_permissions

logger = logging.getLogger('apps')

def generate_id():
    """生成唯一ID"""
    return hashlib.sha256(str(uuid.uuid4()).encode()).hexdigest()[:32]

def execute_build(task, build_number, commit_id, history):
    """执行构建任务"""
    try:
        builder = Builder(task, build_number, commit_id, history)
        builder.execute()
    finally:
        # 无论构建成功、失败或异常，都将构建状态重置为空闲
        from django.db import transaction
        with transaction.atomic():
            # 重新获取任务对象，确保获取最新状态
            from ..models import BuildTask
            BuildTask.objects.filter(task_id=task.task_id).update(building_status='idle')
            logger.info(f"任务 [{task.task_id}] 构建状态已重置为空闲")

@method_decorator(csrf_exempt, name='dispatch')
class BuildTaskView(View):
    @method_decorator(jwt_auth_required)
    def get(self, request, task_id=None):
        """获取构建任务列表或单个任务详情"""
        try:
            # 获取当前用户的权限信息
            user_permissions = get_user_permissions(request.user_id)
            data_permissions = user_permissions.get('data', {})

            # 检查用户是否有构建任务查看权限
            function_permissions = user_permissions.get('function', {})
            build_permissions = function_permissions.get('build_task', [])

            if 'view' not in build_permissions:
                logger.warning(f'用户[{request.user_id}]没有构建任务查看权限')
                return JsonResponse({
                    'code': 403,
                    'message': '没有权限查看构建任务'
                }, status=403)

            # 如果请求参数中包含get_robots=true，则返回通知机器人列表
            if request.GET.get('get_robots') == 'true':
                robots = NotificationRobot.objects.all()
                robot_list = []
                for robot in robots:
                    robot_list.append({
                        'robot_id': robot.robot_id,
                        'type': robot.type,
                        'name': robot.name,
                    })
                return JsonResponse({
                    'code': 200,
                    'message': '获取通知机器人列表成功',
                    'data': robot_list
                })

            # 如果提供了task_id，则返回单个任务详情
            if task_id:
                try:
                    task = BuildTask.objects.select_related(
                        'project',
                        'environment',
                        'git_token',
                        'creator'
                    ).get(task_id=task_id)

                    # 检查是否有权限查看该任务（项目权限和环境权限）
                    # 项目权限检查
                    project_scope = data_permissions.get('project_scope', 'all')
                    if project_scope == 'custom':
                        permitted_project_ids = data_permissions.get('project_ids', [])
                        if task.project and task.project.project_id not in permitted_project_ids:
                            logger.warning(f'用户[{request.user_id}]尝试查看无权限的项目[{task.project.project_id}]的构建任务')
                            return JsonResponse({
                                'code': 403,
                                'message': '没有权限查看该项目的构建任务'
                            }, status=403)

                    # 环境权限检查
                    environment_scope = data_permissions.get('environment_scope', 'all')
                    if environment_scope == 'custom':
                        permitted_environment_types = data_permissions.get('environment_types', [])
                        if task.environment and task.environment.type not in permitted_environment_types:
                            logger.warning(f'用户[{request.user_id}]尝试查看无权限的环境类型[{task.environment.type}]的构建任务')
                            return JsonResponse({
                                'code': 403,
                                'message': '没有权限查看该环境的构建任务'
                            }, status=403)

                    # 获取最新的构建历史
                    latest_build = BuildHistory.objects.filter(task=task).order_by('-build_number').first()

                    # 获取通知机器人详情
                    notification_robots = []
                    if task.notification_channels:
                        robots = NotificationRobot.objects.filter(robot_id__in=task.notification_channels)
                        for robot in robots:
                            notification_robots.append({
                                'robot_id': robot.robot_id,
                                'type': robot.type,
                                'name': robot.name
                            })

                    return JsonResponse({
                        'code': 200,
                        'message': '获取任务详情成功',
                        'data': {
                            'task_id': task.task_id,
                            'name': task.name,
                            'project': {
                                'project_id': task.project.project_id,
                                'name': task.project.name,
                                'repository': task.project.repository
                            } if task.project else None,
                            'environment': {
                                'environment_id': task.environment.environment_id,
                                'name': task.environment.name,
                                'type': task.environment.type
                            } if task.environment else None,
                            'description': task.description,
                            'requirement': task.requirement,
                            'branch': task.branch,
                            'git_token': {
                                'credential_id': task.git_token.credential_id,
                                'name': task.git_token.name
                            } if task.git_token else None,
                            'github_token': {
                                'credential_id': task.github_token.credential_id,
                                'name': task.github_token.name
                            } if task.github_token else None,
                            'stages': task.stages,
                            'parameters': task.parameters,
                            'notification_channels': task.notification_channels,
                            'notification_robots': notification_robots,
                            # 外部脚本库配置
                            'use_external_script': task.use_external_script,
                            'external_script_repo_url': task.external_script_config.get('repo_url', '') if task.external_script_config else '',
                            'external_script_directory': task.external_script_config.get('directory', '') if task.external_script_config else '',
                            'external_script_branch': task.external_script_config.get('branch', '') if task.external_script_config else '',
                            'external_script_token_id': task.external_script_config.get('token_id') if task.external_script_config else None,
                            # 自动构建配置
                            'auto_build_enabled': task.auto_build_enabled,
                            'auto_build_branches': task.auto_build_branches,
                            'webhook_token': task.webhook_token,
                            'status': task.status,
                            'building_status': task.building_status,  # 添加构建状态字段
                            'version': task.version,
                            'last_build_number': task.last_build_number,
                            'total_builds': task.total_builds,
                            'success_builds': task.success_builds,
                            'failure_builds': task.failure_builds,
                            'last_build': {
                                'id': latest_build.history_id,
                                'number': latest_build.build_number,
                                'status': latest_build.status,
                                'time': latest_build.create_time.strftime('%Y-%m-%d %H:%M:%S'),
                                'duration': '未完成' if latest_build.status in ['pending', 'running'] else str(latest_build.build_time.get('total_duration', 0)) + '秒'
                            } if latest_build else None,
                            'creator': {
                                'user_id': task.creator.user_id,
                                'name': task.creator.name
                            } if task.creator else None,
                            'create_time': task.create_time.strftime('%Y-%m-%d %H:%M:%S'),
                            'update_time': task.update_time.strftime('%Y-%m-%d %H:%M:%S')
                        }
                    })
                except BuildTask.DoesNotExist:
                    return JsonResponse({
                        'code': 404,
                        'message': '任务不存在'
                    })

            # 获取查询参数
            project_id = request.GET.get('project_id')
            environment_id = request.GET.get('environment_id')
            name = request.GET.get('name')

            # 构建查询条件
            query = Q()

            # 应用项目权限过滤
            project_scope = data_permissions.get('project_scope', 'all')
            if project_scope == 'custom':
                permitted_project_ids = data_permissions.get('project_ids', [])
                if not permitted_project_ids:
                    # 如果设置了自定义项目权限但列表为空，意味着没有权限查看任何项目
                    logger.info(f'用户[{request.user_id}]没有权限查看任何项目的构建任务')
                    return JsonResponse({
                        'code': 200,
                        'message': '获取任务列表成功',
                        'data': []
                    })

                # 用户只能查看有权限的项目
                if project_id and project_id != 'all':
                    # 如果指定了项目，检查是否有该项目的权限
                    if project_id not in permitted_project_ids:
                        logger.warning(f'用户[{request.user_id}]尝试查看无权限的项目[{project_id}]的构建任务')
                        return JsonResponse({
                            'code': 403,
                            'message': '没有权限查看该项目的构建任务'
                        }, status=403)
                    query &= Q(project__project_id=project_id)
                else:
                    # 如果没有指定项目或选择了全部，则限制为有权限的项目
                    query &= Q(project__project_id__in=permitted_project_ids)
            else:
                # 如果有全部项目权限，并且指定了项目ID
                if project_id and project_id != 'all':
                    query &= Q(project__project_id=project_id)

            # 应用环境权限过滤
            environment_scope = data_permissions.get('environment_scope', 'all')
            if environment_scope == 'custom':
                permitted_environment_types = data_permissions.get('environment_types', [])
                if not permitted_environment_types:
                    # 如果设置了自定义环境权限但列表为空，意味着没有权限查看任何环境
                    logger.info(f'用户[{request.user_id}]没有权限查看任何环境的构建任务')
                    return JsonResponse({
                        'code': 200,
                        'message': '获取任务列表成功',
                        'data': []
                    })

                if environment_id and environment_id != 'all':
                    # 如果指定了环境，需要检查是否在有权限的环境类型中
                    try:
                        env = Environment.objects.get(environment_id=environment_id)
                        if env.type not in permitted_environment_types:
                            logger.warning(f'用户[{request.user_id}]尝试查看无权限的环境[{environment_id}]的构建任务')
                            return JsonResponse({
                                'code': 403,
                                'message': '没有权限查看该环境的构建任务'
                            }, status=403)
                        query &= Q(environment__environment_id=environment_id)
                    except Environment.DoesNotExist:
                        return JsonResponse({
                            'code': 404,
                            'message': '环境不存在'
                        }, status=404)
                else:
                    # 如果没有指定环境或选择了全部，则限制为有权限的环境类型
                    query &= Q(environment__type__in=permitted_environment_types)
            else:
                # 如果有全部环境权限，并且指定了环境ID
                if environment_id and environment_id != 'all':
                    query &= Q(environment__environment_id=environment_id)

            # 添加其他查询条件
            if name:
                query &= Q(name__icontains=name)

            # 查询任务列表
            tasks = BuildTask.objects.select_related(
                'project',
                'environment',
                'creator'
            ).filter(query)

            task_list = []
            for task in tasks:
                # 获取最新的构建历史
                latest_build = BuildHistory.objects.filter(task=task).order_by('-build_number').first()

                task_list.append({
                    'task_id': task.task_id,
                    'name': task.name,
                    'project': {
                        'project_id': task.project.project_id,
                        'name': task.project.name
                    } if task.project else None,
                    'environment': {
                        'environment_id': task.environment.environment_id,
                        'name': task.environment.name,
                        'type': task.environment.type
                    } if task.environment else None,
                    'description': task.description,
                    'branch': task.branch,
                    'status': task.status,
                    'building_status': task.building_status, 
                    'parameters': task.parameters,
                    'version': task.version,
                    'last_build_number': task.last_build_number,
                    'total_builds': task.total_builds,
                    'success_builds': task.success_builds,
                    'failure_builds': task.failure_builds,
                    'last_build': {
                        'id': latest_build.history_id,
                        'number': latest_build.build_number,
                        'status': latest_build.status,
                        'time': latest_build.create_time.strftime('%Y-%m-%d %H:%M:%S'),
                        'duration': '未完成' if latest_build.status in ['pending', 'running'] else str(latest_build.build_time.get('total_duration', 0)) + '秒'
                    } if latest_build else None,
                    'creator': {
                        'user_id': task.creator.user_id,
                        'name': task.creator.name
                    } if task.creator else None,
                    'create_time': task.create_time.strftime('%Y-%m-%d %H:%M:%S'),
                    'update_time': task.update_time.strftime('%Y-%m-%d %H:%M:%S')
                })

            return JsonResponse({
                'code': 200,
                'message': '获取任务列表成功',
                'data': task_list
            })
        except Exception as e:
            logger.error(f'获取构建任务失败: {str(e)}', exc_info=True)
            return JsonResponse({
                'code': 500,
                'message': f'服务器错误: {str(e)}'
            })

    @method_decorator(jwt_auth_required)
    def post(self, request):
        """创建构建任务"""
        try:
            # 获取当前用户的权限信息
            user_permissions = get_user_permissions(request.user_id)
            data_permissions = user_permissions.get('data', {})
            function_permissions = user_permissions.get('function', {})
            build_permissions = function_permissions.get('build_task', [])

            # 检查用户是否有构建任务创建权限
            if 'create' not in build_permissions:
                logger.warning(f'用户[{request.user_id}]没有构建任务创建权限')
                return JsonResponse({
                    'code': 403,
                    'message': '没有权限创建构建任务'
                }, status=403)

            with transaction.atomic():
                data = json.loads(request.body)
                
                name = data.get('name')
                project_id = data.get('project_id')
                environment_id = data.get('environment_id')
                description = data.get('description')
                branch = data.get('branch', 'main')
                git_token_id = data.get('git_token_id')
                github_token_id = data.get('github_token_id')
                stages = data.get('stages')
                parameters = data.get('parameters')
                notification_channels = data.get('notification_channels')
                
                # 自动构建配置
                auto_build_enabled = data.get('auto_build_enabled', False)
                auto_build_branches = data.get('auto_build_branches', [])
                webhook_token = data.get('webhook_token')

                # 外部脚本库配置
                use_external_script = data.get('use_external_script', False)
                external_script_config = None
                if use_external_script:
                    repo_url = data.get('external_script_repo_url', '').strip()
                    directory = data.get('external_script_directory', '').strip()
                    external_script_branch = data.get('external_script_branch', '').strip()
                    token_id = data.get('external_script_token_id')
                    
                    # 验证外部脚本库必填字段
                    if not repo_url:
                        return JsonResponse({
                            'code': 400,
                            'message': '外部脚本库仓库地址不能为空'
                        })
                    if not directory:
                        return JsonResponse({
                            'code': 400,
                            'message': '外部脚本库存放目录不能为空'
                        })
                    if not external_script_branch:
                        return JsonResponse({
                            'code': 400,
                            'message': '外部脚本库分支不能为空'
                        })
                    
                    external_script_config = {
                        'repo_url': repo_url,
                        'directory': directory,
                        'branch': external_script_branch,
                        'token_id': token_id
                    }

                # 验证必填字段
                if not name:
                    return JsonResponse({
                        'code': 400,
                        'message': '任务名称不能为空'
                    })
                if not project_id:
                    return JsonResponse({
                        'code': 400,
                        'message': '项目ID不能为空'
                    })
                if not environment_id:
                    return JsonResponse({
                        'code': 400,
                        'message': '环境ID不能为空'
                    })

                # 验证构建阶段配置
                if not stages:
                    return JsonResponse({
                        'code': 400,
                        'message': '构建阶段不能为空'
                    })

                # 验证参数配置格式
                if parameters:
                    import re
                    for param in parameters:
                        if not param.get('name') or not param.get('choices'):
                            return JsonResponse({
                                'code': 400,
                                'message': '参数名称和可选值不能为空'
                            })
                        
                        # 验证参数名格式（大写字母、数字、下划线）
                        if not re.match(r'^[A-Z_][A-Z0-9_]*$', param['name']):
                            return JsonResponse({
                                'code': 400,
                                'message': f'参数名"{param["name"]}"格式不正确，只能包含大写字母、数字和下划线，且必须以字母或下划线开头'
                            })

                # 验证通知机器人是否存在
                if notification_channels:
                    existing_robots = set(NotificationRobot.objects.filter(
                        robot_id__in=notification_channels
                    ).values_list('robot_id', flat=True))
                    invalid_robots = set(notification_channels) - existing_robots
                    if invalid_robots:
                        return JsonResponse({
                            'code': 400,
                            'message': f'以下机器人不存在: {", ".join(invalid_robots)}'
                        })

                # 检查项目是否存在
                try:
                    project = Project.objects.get(project_id=project_id)
                except Project.DoesNotExist:
                    return JsonResponse({
                        'code': 404,
                        'message': '项目不存在'
                    })

                # 检查环境是否存在
                try:
                    environment = Environment.objects.get(environment_id=environment_id)
                except Environment.DoesNotExist:
                    return JsonResponse({
                        'code': 404,
                        'message': '环境不存在'
                    })

                # 检查GitLab Token凭证是否存在
                git_token = None
                if git_token_id:
                    try:
                        git_token = GitlabTokenCredential.objects.get(credential_id=git_token_id)
                    except GitlabTokenCredential.DoesNotExist:
                        return JsonResponse({
                            'code': 404,
                            'message': 'GitLab Token凭证不存在'
                        })

                # 检查GitHub Token凭证是否存在
                github_token = None
                if github_token_id:
                    try:
                        github_token = GitHubTokenCredential.objects.get(credential_id=github_token_id)
                    except GitHubTokenCredential.DoesNotExist:
                        return JsonResponse({
                            'code': 404,
                            'message': 'GitHub Token凭证不存在'
                        })

                # 如果启用自动构建但没有webhook_token，生成一个
                if auto_build_enabled and not webhook_token:
                    import secrets
                    webhook_token = secrets.token_urlsafe(32)

                # 创建构建任务
                creator = User.objects.get(user_id=request.user_id)
                task = BuildTask.objects.create(
                    task_id=generate_id(),
                    name=name,
                    project=project,
                    environment=environment,
                    description=description,
                    branch=branch,
                    git_token=git_token,
                    github_token=github_token,
                    stages=stages,
                    parameters=parameters,
                    notification_channels=notification_channels,
                    use_external_script=use_external_script,
                    external_script_config=external_script_config,
                    auto_build_enabled=auto_build_enabled,
                    auto_build_branches=auto_build_branches,
                    webhook_token=webhook_token,
                    creator=creator
                )

                return JsonResponse({
                    'code': 200,
                    'message': '创建构建任务成功',
                    'data': {
                        'task_id': task.task_id,
                        'name': task.name
                    }
                })
        except Exception as e:
            logger.error(f'创建构建任务失败: {str(e)}', exc_info=True)
            return JsonResponse({
                'code': 500,
                'message': f'服务器错误: {str(e)}'
            })

    @method_decorator(jwt_auth_required)
    def put(self, request):
        """更新构建任务"""
        try:
            # 获取当前用户的权限信息
            user_permissions = get_user_permissions(request.user_id)
            data_permissions = user_permissions.get('data', {})
            function_permissions = user_permissions.get('function', {})
            build_permissions = function_permissions.get('build_task', [])

            # 检查用户是否有构建任务编辑权限
            if 'edit' not in build_permissions:
                logger.warning(f'用户[{request.user_id}]没有构建任务编辑权限')
                return JsonResponse({
                    'code': 403,
                    'message': '没有权限编辑构建任务'
                }, status=403)

            with transaction.atomic():
                data = json.loads(request.body)
                
                task_id = data.get('task_id')
                name = data.get('name')
                project_id = data.get('project_id')
                environment_id = data.get('environment_id')
                description = data.get('description')
                branch = data.get('branch')
                git_token_id = data.get('git_token_id')
                github_token_id = data.get('github_token_id')
                stages = data.get('stages')
                parameters = data.get('parameters')
                notification_channels = data.get('notification_channels')
                status = data.get('status')

                # 自动构建配置
                auto_build_enabled = data.get('auto_build_enabled')
                auto_build_branches = data.get('auto_build_branches')
                webhook_token = data.get('webhook_token')

                # 外部脚本库配置
                use_external_script = data.get('use_external_script')
                external_script_config = None
                if 'use_external_script' in data:
                    if use_external_script:
                        repo_url = data.get('external_script_repo_url', '').strip()
                        directory = data.get('external_script_directory', '').strip()
                        external_script_branch = data.get('external_script_branch', '').strip()
                        token_id = data.get('external_script_token_id')

                        # 验证外部脚本库必填字段
                        if not repo_url:
                            return JsonResponse({
                                'code': 400,
                                'message': '外部脚本库仓库地址不能为空'
                            })
                        if not directory:
                            return JsonResponse({
                                'code': 400,
                                'message': '外部脚本库存放目录不能为空'
                            })
                        if not external_script_branch:
                            return JsonResponse({
                                'code': 400,
                                'message': '外部脚本库分支不能为空'
                            })

                        external_script_config = {
                            'repo_url': repo_url,
                            'directory': directory,
                            'branch': external_script_branch,
                            'token_id': token_id
                        }
                    else:
                        external_script_config = {}

                # 验证必填字段
                if not task_id:
                    return JsonResponse({
                        'code': 400,
                        'message': '任务ID不能为空'
                    })

                # 获取任务对象
                try:
                    task = BuildTask.objects.get(task_id=task_id)
                except BuildTask.DoesNotExist:
                    return JsonResponse({
                        'code': 404,
                        'message': '任务不存在'
                    })

                # 检查用户是否有权限编辑该任务
                # 项目权限检查
                project_scope = data_permissions.get('project_scope', 'all')
                if project_scope == 'custom' and task.project:
                    permitted_project_ids = data_permissions.get('project_ids', [])
                    if task.project.project_id not in permitted_project_ids:
                        logger.warning(f'用户[{request.user_id}]尝试编辑无权限的项目[{task.project.project_id}]的构建任务')
                        return JsonResponse({
                            'code': 403,
                            'message': '没有权限编辑该项目的构建任务'
                        }, status=403)

                # 环境权限检查
                environment_scope = data_permissions.get('environment_scope', 'all')
                if environment_scope == 'custom' and task.environment:
                    permitted_environment_ids = data_permissions.get('environment_ids', [])
                    if task.environment.environment_id not in permitted_environment_ids:
                        logger.warning(f'用户[{request.user_id}]尝试编辑无权限的环境[{task.environment.environment_id}]的构建任务')
                        return JsonResponse({
                            'code': 403,
                            'message': '没有权限编辑该环境的构建任务'
                        }, status=403)

                # 更新任务字段
                update_fields = []
                if name is not None:
                    task.name = name
                    update_fields.append('name')
                if project_id is not None:
                    try:
                        project = Project.objects.get(project_id=project_id)
                        task.project = project
                        update_fields.append('project')
                    except Project.DoesNotExist:
                        return JsonResponse({
                            'code': 404,
                            'message': '项目不存在'
                        })
                if environment_id is not None:
                    try:
                        environment = Environment.objects.get(environment_id=environment_id)
                        task.environment = environment
                        update_fields.append('environment')
                    except Environment.DoesNotExist:
                        return JsonResponse({
                            'code': 404,
                            'message': '环境不存在'
                        })
                if description is not None:
                    task.description = description
                    update_fields.append('description')
                if branch is not None:
                    task.branch = branch
                    update_fields.append('branch')

                # 更新GitLab Token
                if git_token_id is not None:
                    if git_token_id:
                        try:
                            git_token = GitlabTokenCredential.objects.get(credential_id=git_token_id)
                            task.git_token = git_token
                        except GitlabTokenCredential.DoesNotExist:
                            return JsonResponse({
                                'code': 404,
                                'message': 'GitLab Token凭证不存在'
                            })
                    else:
                        task.git_token = None
                    update_fields.append('git_token')

                # 更新GitHub Token
                if github_token_id is not None:
                    if github_token_id:
                        try:
                            github_token = GitHubTokenCredential.objects.get(credential_id=github_token_id)
                            task.github_token = github_token
                        except GitHubTokenCredential.DoesNotExist:
                            return JsonResponse({
                                'code': 404,
                                'message': 'GitHub Token凭证不存在'
                            })
                    else:
                        task.github_token = None
                    update_fields.append('github_token')

                if stages is not None:
                    task.stages = stages
                    update_fields.append('stages')
                if parameters is not None:
                    task.parameters = parameters
                    update_fields.append('parameters')
                if notification_channels is not None:
                    task.notification_channels = notification_channels
                    update_fields.append('notification_channels')
                if status is not None:
                    task.status = status
                    update_fields.append('status')
                if auto_build_enabled is not None:
                    task.auto_build_enabled = auto_build_enabled
                    update_fields.append('auto_build_enabled')
                if auto_build_branches is not None:
                    task.auto_build_branches = auto_build_branches
                    update_fields.append('auto_build_branches')
                if webhook_token is not None:
                    task.webhook_token = webhook_token
                    update_fields.append('webhook_token')
                if external_script_config is not None:
                    task.external_script_config = external_script_config
                    update_fields.append('external_script_config')
                if use_external_script is not None:
                    task.use_external_script = use_external_script
                    update_fields.append('use_external_script')

                # 保存更新
                if update_fields:
                    task.save(update_fields=update_fields)

                return JsonResponse({
                    'code': 200,
                    'message': '更新构建任务成功',
                    'data': {
                        'task_id': task.task_id
                    }
                })
        except Exception as e:
            logger.error(f'更新构建任务失败: {str(e)}', exc_info=True)
            return JsonResponse({
                'code': 500,
                'message': f'服务器错误: {str(e)}'
            })

    @method_decorator(jwt_auth_required)
    def delete(self, request):
        """删除构建任务"""
        try:
            with transaction.atomic():
                data = json.loads(request.body)
                task_id = data.get('task_id')

                if not task_id:
                    return JsonResponse({
                        'code': 400,
                        'message': '任务ID不能为空'
                    })

                try:
                    task = BuildTask.objects.get(task_id=task_id)
                    task.delete()
                    return JsonResponse({
                        'code': 200,
                        'message': '删除构建任务成功'
                    })
                except BuildTask.DoesNotExist:
                    return JsonResponse({
                        'code': 404,
                        'message': '任务不存在'
                    })
        except Exception as e:
            logger.error(f'删除构建任务失败: {str(e)}', exc_info=True)
            return JsonResponse({
                'code': 500,
                'message': f'服务器错误: {str(e)}'
            })

@method_decorator(csrf_exempt, name='dispatch')
class BuildExecuteView(View):
    @method_decorator(jwt_auth_required)
    def post(self, request):
        """执行构建"""
        try:
            # 获取当前用户的权限信息
            user_permissions = get_user_permissions(request.user_id)
            data_permissions = user_permissions.get('data', {})

            # 检查用户是否有执行构建权限
            function_permissions = user_permissions.get('function', {})
            build_permissions = function_permissions.get('build_task', [])

            if 'execute' not in build_permissions:
                logger.warning(f'用户[{request.user_id}]没有执行构建权限')
                return JsonResponse({
                    'code': 403,
                    'message': '没有权限执行构建任务'
                }, status=403)

            data = json.loads(request.body)
            task_id = data.get('task_id')
            branch = data.get('branch')  # 获取用户选择的分支
            commit_id = data.get('commit_id')
            version = data.get('version') 
            requirement = data.get('requirement')
            parameter_values = data.get('parameter_values', {})

            if not task_id:
                return JsonResponse({
                    'code': 400,
                    'message': '任务ID不能为空'
                })

            try:
                task = BuildTask.objects.select_related('project', 'environment').get(task_id=task_id)
            except BuildTask.DoesNotExist:
                return JsonResponse({
                    'code': 404,
                    'message': '任务不存在'
                })

            # 检查是否有权限执行该任务
            # 项目权限检查
            project_scope = data_permissions.get('project_scope', 'all')
            if project_scope == 'custom':
                permitted_project_ids = data_permissions.get('project_ids', [])
                if task.project and task.project.project_id not in permitted_project_ids:
                    logger.warning(f'用户[{request.user_id}]尝试执行无权限的项目[{task.project.project_id}]的构建任务')
                    return JsonResponse({
                        'code': 403,
                        'message': '没有权限执行该项目的构建任务'
                    }, status=403)

            # 环境权限检查
            environment_scope = data_permissions.get('environment_scope', 'all')
            if environment_scope == 'custom':
                permitted_environment_types = data_permissions.get('environment_types', [])
                if task.environment and task.environment.type not in permitted_environment_types:
                    logger.warning(f'用户[{request.user_id}]尝试执行无权限的环境类型[{task.environment.type}]的构建任务')
                    return JsonResponse({
                        'code': 403,
                        'message': '没有权限执行该环境的构建任务'
                    }, status=403)

            # 根据环境类型检查必要参数
            env_type = task.environment.type if task.environment else None

            if env_type in ['development', 'testing']:
                # 开发环境和测试环境需要分支和commit_id
                if not branch:
                    return JsonResponse({
                        'code': 400,
                        'message': '分支不能为空'
                    })

                if not commit_id:
                    return JsonResponse({
                        'code': 400,
                        'message': 'Commit ID不能为空'
                    })
            elif env_type in ['staging', 'production']:
                if version:
                    parts = version.split('_')
                    if len(parts) == 2 and len(parts[1]) >= 8:
                        commit_id = parts[1]
                    else:
                        return JsonResponse({
                            'code': 400,
                            'message': '版本号格式不正确，应为：YYYYMMDDHHmmSS_commitId'
                        })
                elif branch and commit_id:
                    pass  # 参数验证通过，继续执行
                else:
                    return JsonResponse({
                        'code': 400,
                        'message': '预发布和生产环境请选择构建方式：输入版本号或选择分支进行重新构建'
                    })

            if not requirement:
                return JsonResponse({
                    'code': 400,
                    'message': '构建需求描述不能为空'
                })

            # 验证参数值是否合法
            if task.parameters and parameter_values:
                task_parameters = {p['name']: p['choices'] for p in task.parameters}
                for param_name, selected_values in parameter_values.items():
                    if param_name not in task_parameters:
                        return JsonResponse({
                            'code': 400,
                            'message': f'未定义的参数: {param_name}'
                        })
                    
                    for value in selected_values:
                        if value not in task_parameters[param_name]:
                            return JsonResponse({
                                'code': 400,
                                'message': f'参数{param_name}的值"{value}"不在可选范围内'
                            })

            # 检查任务的构建状态
            if task.building_status == 'building':
                return JsonResponse({
                    'code': 400,
                    'message': '当前任务正在构建中，请等待构建完成后再试'
                })

            running_build = BuildHistory.objects.filter(
                task_id=task_id,
                status__in=['pending', 'running']
            ).exists()

            if running_build:
                # 如果有正在进行的构建，但building_status不是building，则修正状态
                BuildTask.objects.filter(task_id=task_id).update(building_status='building')
                return JsonResponse({
                    'code': 400,
                    'message': '当前任务有正在进行的构建，请等待构建完成后再试'
                })

            if task.status == 'disabled':
                return JsonResponse({
                    'code': 400,
                    'message': '任务已禁用'
                })

            # 生成构建号
            build_number = task.last_build_number + 1

            # 创建构建历史记录
            history = BuildHistory.objects.create(
                history_id=generate_id(),
                task=task,
                build_number=build_number,
                branch=branch if branch else '',
                commit_id=commit_id,
                version=version if version else None,
                status='pending',  # 初始状态为等待中
                requirement=requirement,
                parameter_values=parameter_values,
                operator=User.objects.get(user_id=request.user_id)  # 记录构建人
            )

            # 更新任务状态、构建号和构建状态
            BuildTask.objects.filter(task_id=task_id).update(
                last_build_number=build_number,
                total_builds=F('total_builds') + 1,
                building_status='building'  # 设置为构建中状态
            )

            # 在新线程中执行构建
            build_thread = threading.Thread(
                target=execute_build,
                args=(task, build_number, commit_id, history)
            )
            build_thread.start()

            return JsonResponse({
                'code': 200,
                'message': '开始构建',
                'data': {
                    'build_number': build_number,
                    'history_id': history.history_id
                }
            })
        except Exception as e:
            logger.error(f'执行构建失败: {str(e)}', exc_info=True)
            return JsonResponse({
                'code': 500,
                'message': f'服务器错误: {str(e)}'
            })

    @method_decorator(jwt_auth_required)
    def put(self, request):
        """停止构建"""
        try:
            data = json.loads(request.body)
            history_id = data.get('history_id')

            if not history_id:
                return JsonResponse({
                    'code': 400,
                    'message': '历史ID不能为空'
                })

            try:
                history = BuildHistory.objects.get(history_id=history_id)
            except BuildHistory.DoesNotExist:
                return JsonResponse({
                    'code': 404,
                    'message': '构建历史不存在'
                })

            # 只有进行中的构建可以停止
            if history.status not in ['pending', 'running']:
                return JsonResponse({
                    'code': 400,
                    'message': '只能停止进行中的构建'
                })

            # 更新构建状态为terminated
            history.status = 'terminated'

            # 如果构建日志存在，追加终止消息
            if history.build_log:
                history.build_log += "\n[系统] 构建被手动终止\n"
            else:
                history.build_log = "[系统] 构建被手动终止\n"

            # 更新构建时间
            if not history.build_time:
                history.build_time = {}

            if 'start_time' in history.build_time and 'total_duration' not in history.build_time:
                # 计算从开始到现在的持续时间
                start_time = datetime.strptime(history.build_time['start_time'], '%Y-%m-%d %H:%M:%S')
                duration = int((datetime.now() - start_time).total_seconds())
                history.build_time['total_duration'] = str(duration)
                history.build_time['end_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            history.save()

            # 更新任务统计信息和构建状态
            BuildTask.objects.filter(task_id=history.task.task_id).update(
                building_status='idle'  # 重置构建状态为空闲
            )

            return JsonResponse({
                'code': 200,
                'message': '构建已终止'
            })

        except Exception as e:
            logger.error(f'停止构建失败: {str(e)}', exc_info=True)
            return JsonResponse({
                'code': 500,
                'message': f'服务器错误: {str(e)}'
            })