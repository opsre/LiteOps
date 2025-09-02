from django.db import models

class User(models.Model):
    """
    用户表
    """
    id = models.AutoField(primary_key=True)
    user_id = models.CharField(max_length=32, unique=True, null=True, verbose_name='用户ID')
    username = models.CharField(max_length=50, unique=True, null=True, verbose_name='用户名')
    name = models.CharField(max_length=50, null=True, verbose_name='姓名')
    password = models.CharField(max_length=128, null=True, verbose_name='密码')
    email = models.EmailField(max_length=100, unique=True, null=True, verbose_name='邮箱')
    user_type = models.CharField(max_length=20, default='system', null=True, verbose_name='用户类型')
    ldap_dn = models.CharField(max_length=255, null=True, blank=True, verbose_name='LDAP DN')
    status = models.SmallIntegerField(null=True, verbose_name='状态')
    login_time = models.DateTimeField(null=True, verbose_name='最后登录时间')
    create_time = models.DateTimeField(auto_now_add=True, null=True, verbose_name='创建时间')
    update_time = models.DateTimeField(auto_now=True, null=True, verbose_name='更新时间')

    class Meta:
        db_table = 'user'
        verbose_name = '用户'
        verbose_name_plural = verbose_name
        ordering = ['-create_time']

    def __str__(self):
        return self.username


class Role(models.Model):
    """
    角色表
    """
    id = models.AutoField(primary_key=True)
    role_id = models.CharField(max_length=32, unique=True, null=True, verbose_name='角色ID')
    name = models.CharField(max_length=50, unique=True, null=True, verbose_name='角色名称')
    description = models.TextField(null=True, blank=True, verbose_name='角色描述')
    permissions = models.JSONField(default=dict, null=True, verbose_name='权限配置')
    creator = models.ForeignKey('User', on_delete=models.CASCADE, to_field='user_id', null=True, verbose_name='创建者')
    create_time = models.DateTimeField(auto_now_add=True, null=True, verbose_name='创建时间')
    update_time = models.DateTimeField(auto_now=True, null=True, verbose_name='更新时间')

    class Meta:
        db_table = 'role'
        verbose_name = '角色'
        verbose_name_plural = verbose_name
        ordering = ['-create_time']

    def __str__(self):
        return self.name


class UserRole(models.Model):
    """
    用户角色关联表
    """
    id = models.AutoField(primary_key=True)
    user = models.ForeignKey('User', on_delete=models.CASCADE, to_field='user_id', null=True, verbose_name='用户')
    role = models.ForeignKey('Role', on_delete=models.CASCADE, to_field='role_id', null=True, verbose_name='角色')
    create_time = models.DateTimeField(auto_now_add=True, null=True, verbose_name='创建时间')
    update_time = models.DateTimeField(auto_now=True, null=True, verbose_name='更新时间')

    class Meta:
        db_table = 'user_role'
        verbose_name = '用户角色关联'
        verbose_name_plural = verbose_name
        ordering = ['-create_time']
        unique_together = ['user', 'role']  # 确保用户和角色的组合唯一

    def __str__(self):
        return f"{self.user.username} - {self.role.name}"


class UserToken(models.Model):
    """
    用户Token表
    """
    id = models.AutoField(primary_key=True)
    token_id = models.CharField(max_length=32, unique=True, null=True, verbose_name='TokenID')
    user = models.ForeignKey('User', on_delete=models.CASCADE, to_field='user_id', null=True, verbose_name='用户')
    token = models.CharField(max_length=256, null=True, verbose_name='Token信息')
    create_time = models.DateTimeField(auto_now_add=True, null=True, verbose_name='创建时间')
    update_time = models.DateTimeField(auto_now=True, null=True, verbose_name='更新时间')

    class Meta:
        db_table = 'user_token'
        verbose_name = '用户Token'
        verbose_name_plural = verbose_name
        ordering = ['-create_time']

    def __str__(self):
        return f"{self.user.username}'s token"


class Project(models.Model):
    """
    项目表 - 包含项目基本信息和服务信息
    """
    id = models.AutoField(primary_key=True)
    project_id = models.CharField(max_length=32, unique=True, null=True, verbose_name='项目ID')
    name = models.CharField(max_length=50, null=True, verbose_name='项目名称')
    description = models.TextField(null=True, blank=True, verbose_name='项目描述')
    category = models.CharField(max_length=20, null=True, verbose_name='服务类别')  # frontend, backend, mobile
    repository = models.CharField(max_length=255, null=True, verbose_name='代码仓库地址')
    creator = models.ForeignKey('User', on_delete=models.CASCADE, to_field='user_id', null=True, verbose_name='创建者')
    create_time = models.DateTimeField(auto_now_add=True, null=True, verbose_name='创建时间')
    update_time = models.DateTimeField(auto_now=True, null=True, verbose_name='更新时间')

    class Meta:
        db_table = 'project'
        verbose_name = '项目'
        verbose_name_plural = verbose_name
        ordering = ['-create_time']

    def __str__(self):
        return self.name


class GitlabTokenCredential(models.Model):
    """
    GitLab Token凭证表
    """
    id = models.AutoField(primary_key=True)
    credential_id = models.CharField(max_length=32, unique=True, null=True, verbose_name='凭证ID')
    name = models.CharField(max_length=50, null=True, verbose_name='凭证名称')
    description = models.TextField(null=True, blank=True, verbose_name='凭证描述')
    token = models.CharField(max_length=255, null=True, verbose_name='GitLab Token')
    creator = models.ForeignKey('User', on_delete=models.CASCADE, to_field='user_id', null=True, verbose_name='创建者')
    create_time = models.DateTimeField(auto_now_add=True, null=True, verbose_name='创建时间')
    update_time = models.DateTimeField(auto_now=True, null=True, verbose_name='更新时间')

    class Meta:
        db_table = 'gitlab_token_credential'
        verbose_name = 'GitLab Token凭证'
        verbose_name_plural = verbose_name
        ordering = ['-create_time']

    def __str__(self):
        return self.name


class GitHubTokenCredential(models.Model):
    """
    GitHub Token凭证表
    """
    id = models.AutoField(primary_key=True)
    credential_id = models.CharField(max_length=32, unique=True, null=True, verbose_name='凭证ID')
    name = models.CharField(max_length=50, null=True, verbose_name='凭证名称')
    description = models.TextField(null=True, blank=True, verbose_name='凭证描述')
    token = models.CharField(max_length=255, null=True, verbose_name='GitHub Token')
    creator = models.ForeignKey('User', on_delete=models.CASCADE, to_field='user_id', null=True, verbose_name='创建者')
    create_time = models.DateTimeField(auto_now_add=True, null=True, verbose_name='创建时间')
    update_time = models.DateTimeField(auto_now=True, null=True, verbose_name='更新时间')

    class Meta:
        db_table = 'github_token_credential'
        verbose_name = 'GitHub Token凭证'
        verbose_name_plural = verbose_name
        ordering = ['-create_time']

    def __str__(self):
        return self.name


class SSHKeyCredential(models.Model):
    """
    SSH密钥凭证表
    """
    id = models.AutoField(primary_key=True)
    credential_id = models.CharField(max_length=32, unique=True, null=True, verbose_name='凭证ID')
    name = models.CharField(max_length=50, null=True, verbose_name='凭证名称')
    description = models.TextField(null=True, blank=True, verbose_name='凭证描述')
    private_key = models.TextField(null=True, verbose_name='SSH私钥内容')
    passphrase = models.CharField(max_length=255, null=True, blank=True, verbose_name='私钥密码 (可选)') 
    creator = models.ForeignKey('User', on_delete=models.CASCADE, to_field='user_id', null=True, verbose_name='创建者')
    create_time = models.DateTimeField(auto_now_add=True, null=True, verbose_name='创建时间')
    update_time = models.DateTimeField(auto_now=True, null=True, verbose_name='更新时间')

    class Meta:
        db_table = 'ssh_key_credential'
        verbose_name = 'SSH密钥凭证'
        verbose_name_plural = verbose_name
        ordering = ['-create_time']

    def __str__(self):
        return self.name


class KubeconfigCredential(models.Model):
    """
    Kubeconfig访问凭证表
    """
    id = models.AutoField(primary_key=True)
    credential_id = models.CharField(max_length=32, unique=True, null=True, verbose_name='凭证ID')
    name = models.CharField(max_length=50, null=True, verbose_name='凭证名称')
    description = models.TextField(null=True, blank=True, verbose_name='凭证描述')
    kubeconfig_content = models.TextField(null=True, verbose_name='Kubeconfig文件内容')
    cluster_name = models.CharField(max_length=100, null=True, verbose_name='集群名称')  # 用于显示和区分
    context_name = models.CharField(max_length=100, null=True, verbose_name='上下文名称')  # kubectl使用的context名称
    creator = models.ForeignKey('User', on_delete=models.CASCADE, to_field='user_id', null=True, verbose_name='创建者')
    create_time = models.DateTimeField(auto_now_add=True, null=True, verbose_name='创建时间')
    update_time = models.DateTimeField(auto_now=True, null=True, verbose_name='更新时间')

    class Meta:
        db_table = 'kubeconfig_credential'
        verbose_name = 'Kubeconfig访问凭证'
        verbose_name_plural = verbose_name
        ordering = ['-create_time']

    def __str__(self):
        return self.name


class Environment(models.Model):
    """
    环境配置表 - 用于管理不同的部署环境（如开发、测试、预发布、生产等）
    """
    id = models.AutoField(primary_key=True)
    environment_id = models.CharField(max_length=32, unique=True, null=True, verbose_name='环境ID')
    name = models.CharField(max_length=50, null=True, verbose_name='环境名称')
    type = models.CharField(max_length=20, null=True, verbose_name='环境类型')  # development, testing, staging, production
    description = models.TextField(null=True, blank=True, verbose_name='环境描述')
    creator = models.ForeignKey('User', on_delete=models.CASCADE, to_field='user_id', null=True, verbose_name='创建者')
    create_time = models.DateTimeField(auto_now_add=True, null=True, verbose_name='创建时间')
    update_time = models.DateTimeField(auto_now=True, null=True, verbose_name='更新时间')

    class Meta:
        db_table = 'environment'
        verbose_name = '环境配置'
        verbose_name_plural = verbose_name
        ordering = ['-create_time']

    def __str__(self):
        return self.name


class BuildTask(models.Model):
    """构建任务表"""
    id = models.AutoField(primary_key=True)
    task_id = models.CharField(max_length=32, unique=True, null=True, verbose_name='任务ID')
    name = models.CharField(max_length=100, null=True, verbose_name='任务名称')
    project = models.ForeignKey('Project', on_delete=models.CASCADE, to_field='project_id', null=True, verbose_name='所属项目')
    environment = models.ForeignKey('Environment', on_delete=models.CASCADE, to_field='environment_id', null=True, verbose_name='构建环境')
    description = models.TextField(null=True, blank=True, verbose_name='任务描述')
    requirement = models.TextField(null=True, blank=True, verbose_name='构建需求描述')
    branch = models.CharField(max_length=100, default='main', null=True, verbose_name='默认分支')
    git_token = models.ForeignKey('GitlabTokenCredential', on_delete=models.SET_NULL, to_field='credential_id', null=True, verbose_name='GitLab Token')
    github_token = models.ForeignKey('GitHubTokenCredential', on_delete=models.SET_NULL, to_field='credential_id', null=True, verbose_name='GitHub Token')
    version = models.CharField(max_length=50, null=True, blank=True, verbose_name='构建版本号')

    # 构建阶段
    stages = models.JSONField(default=list, verbose_name='构建阶段')

    # 构建参数配置
    parameters = models.JSONField(default=list, verbose_name='构建参数配置')

    # 外部脚本库配置
    use_external_script = models.BooleanField(default=False, verbose_name='使用外部脚本库')
    external_script_config = models.JSONField(default=dict, verbose_name='外部脚本库配置')

    # 构建时间信息（使用JSON存储）
    build_time = models.JSONField(default=dict, verbose_name='构建时间信息')

    # 构建后操作
    notification_channels = models.JSONField(default=list, verbose_name='通知方式')

    # 自动构建配置
    auto_build_enabled = models.BooleanField(default=False, verbose_name='启用自动构建')
    auto_build_branches = models.JSONField(default=list, verbose_name='自动构建分支')
    webhook_token = models.CharField(max_length=64, null=True, blank=True, verbose_name='Webhook验证Token')

    # 状态和统计
    status = models.CharField(max_length=20, default='created', null=True, verbose_name='任务状态')  # created, disabled
    building_status = models.CharField(max_length=20, default='idle', null=True, verbose_name='构建状态')  # idle, building
    last_build_number = models.IntegerField(default=0, verbose_name='最后构建号')
    total_builds = models.IntegerField(default=0, verbose_name='总构建次数')
    success_builds = models.IntegerField(default=0, verbose_name='成功构建次数')
    failure_builds = models.IntegerField(default=0, verbose_name='失败构建次数')

    creator = models.ForeignKey('User', on_delete=models.CASCADE, to_field='user_id', null=True, verbose_name='创建者')
    create_time = models.DateTimeField(auto_now_add=True, null=True, verbose_name='创建时间')
    update_time = models.DateTimeField(auto_now=True, null=True, verbose_name='更新时间')

    class Meta:
        db_table = 'build_task'
        verbose_name = '构建任务'
        verbose_name_plural = verbose_name
        ordering = ['-create_time']


class BuildHistory(models.Model):
    """构建历史表"""
    id = models.AutoField(primary_key=True)
    history_id = models.CharField(max_length=32, unique=True, null=True, verbose_name='历史ID')
    task = models.ForeignKey('BuildTask', on_delete=models.CASCADE, to_field='task_id', null=True, verbose_name='构建任务')
    build_number = models.IntegerField(verbose_name='构建序号')
    branch = models.CharField(max_length=100, null=True, verbose_name='构建分支')
    commit_id = models.CharField(max_length=40, null=True, verbose_name='Git Commit ID')
    version = models.CharField(max_length=50, null=True, verbose_name='构建版本')
    status = models.CharField(max_length=20, default='pending', verbose_name='构建状态')  # pending, running, success, failed, terminated
    requirement = models.TextField(null=True, blank=True, verbose_name='构建需求描述')
    build_log = models.TextField(null=True, blank=True, verbose_name='构建日志')
    stages = models.JSONField(default=list, verbose_name='构建阶段')
    parameter_values = models.JSONField(default=dict, verbose_name='构建参数值')
    build_time = models.JSONField(default=dict, verbose_name='构建时间信息')

    operator = models.ForeignKey('User', on_delete=models.SET_NULL, to_field='user_id', null=True, verbose_name='构建人')
    create_time = models.DateTimeField(auto_now_add=True, null=True, verbose_name='创建时间')
    update_time = models.DateTimeField(auto_now=True, null=True, verbose_name='更新时间')

    class Meta:
        db_table = 'build_history'
        verbose_name = '构建历史'
        verbose_name_plural = verbose_name
        ordering = ['-create_time']
        unique_together = ['task', 'build_number'] 

    def __str__(self):
        return f"{self.task.name} #{self.build_number}"


class NotificationRobot(models.Model):
    """通知机器人表"""
    id = models.AutoField(primary_key=True)
    robot_id = models.CharField(max_length=32, unique=True, null=True, verbose_name='机器人ID')
    type = models.CharField(max_length=20, null=True, verbose_name='机器人类型')  # dingtalk, wecom, feishu
    name = models.CharField(max_length=50, null=True, verbose_name='机器人名称')
    webhook = models.CharField(max_length=255, null=True, verbose_name='Webhook地址')
    security_type = models.CharField(max_length=20, null=True, verbose_name='安全设置类型')  # none, secret, keyword, ip
    secret = models.CharField(max_length=255, null=True, blank=True, verbose_name='加签密钥')
    keywords = models.JSONField(default=list, null=True, blank=True, verbose_name='自定义关键词')
    ip_list = models.JSONField(default=list, null=True, blank=True, verbose_name='IP白名单')
    remark = models.TextField(null=True, blank=True, verbose_name='备注')
    creator = models.ForeignKey('User', on_delete=models.CASCADE, to_field='user_id', null=True, verbose_name='创建者')
    create_time = models.DateTimeField(auto_now_add=True, null=True, verbose_name='创建时间')
    update_time = models.DateTimeField(auto_now=True, null=True, verbose_name='更新时间')

    class Meta:
        db_table = 'notification_robot'
        verbose_name = '通知机器人'
        verbose_name_plural = verbose_name
        ordering = ['-create_time']

    def __str__(self):
        return f"{self.name} ({self.type})"


class LoginLog(models.Model):
    """
    登录日志表
    """
    id = models.AutoField(primary_key=True)
    log_id = models.CharField(max_length=32, unique=True, null=True, verbose_name='日志ID')
    user = models.ForeignKey('User', on_delete=models.CASCADE, to_field='user_id', null=True, verbose_name='用户')
    ip_address = models.CharField(max_length=50, null=True, verbose_name='IP地址')
    user_agent = models.TextField(null=True, blank=True, verbose_name='用户代理')
    status = models.CharField(max_length=20, null=True, verbose_name='登录状态')  # success, failed
    fail_reason = models.CharField(max_length=100, null=True, blank=True, verbose_name='失败原因')
    login_time = models.DateTimeField(auto_now_add=True, null=True, verbose_name='登录时间')

    class Meta:
        db_table = 'login_log'
        verbose_name = '登录日志'
        verbose_name_plural = verbose_name
        ordering = ['-login_time']

    def __str__(self):
        return f"{self.user.username} - {self.login_time}"


class SecurityConfig(models.Model):
    """
    安全配置表 - 存储系统安全策略配置
    """
    id = models.AutoField(primary_key=True)
    min_password_length = models.IntegerField(default=8, verbose_name='密码最小长度')
    password_complexity = models.JSONField(default=list, verbose_name='密码复杂度要求', help_text='包含: uppercase, lowercase, number, special')
    session_timeout = models.IntegerField(default=120, verbose_name='会话超时时间(分钟)')
    max_login_attempts = models.IntegerField(default=5, verbose_name='最大登录尝试次数')
    lockout_duration = models.IntegerField(default=30, verbose_name='账户锁定时间(分钟)')
    enable_2fa = models.BooleanField(default=False, verbose_name='启用双因子认证')
    # 水印配置
    watermark_enabled = models.BooleanField(default=True, verbose_name='启用水印')
    watermark_content = models.TextField(default='胡图图不涂涂', verbose_name='水印内容')
    watermark_show_time = models.BooleanField(default=False, verbose_name='显示时间水印')
    watermark_show_username = models.BooleanField(default=False, verbose_name='显示用户名水印')
    update_time = models.DateTimeField(auto_now=True, null=True, verbose_name='更新时间')

    class Meta:
        db_table = 'security_config'
        verbose_name = '安全配置'
        verbose_name_plural = verbose_name

    def __str__(self):
        return "系统安全配置"


class LoginAttempt(models.Model):
    """
    登录尝试记录表 - 用于跟踪用户登录失败次数和账户锁定状态
    """
    id = models.AutoField(primary_key=True)
    user = models.ForeignKey('User', on_delete=models.CASCADE, to_field='user_id', null=True, verbose_name='用户')
    ip_address = models.CharField(max_length=50, null=True, verbose_name='IP地址')
    failed_attempts = models.IntegerField(default=0, verbose_name='失败尝试次数')
    locked_until = models.DateTimeField(null=True, blank=True, verbose_name='锁定到期时间')
    last_attempt_time = models.DateTimeField(auto_now=True, verbose_name='最后尝试时间')
    create_time = models.DateTimeField(auto_now_add=True, null=True, verbose_name='创建时间')

    class Meta:
        db_table = 'login_attempt'
        verbose_name = '登录尝试记录'
        verbose_name_plural = verbose_name
        unique_together = ['user', 'ip_address']  # 确保用户和IP组合唯一

    def __str__(self):
        return f"{self.user.username if self.user else 'Unknown'} - {self.ip_address}"


class LDAPConfig(models.Model):
    """
    LDAP配置表 - 存储LDAP服务器配置信息
    """
    id = models.AutoField(primary_key=True)
    enabled = models.BooleanField(default=False, verbose_name='启用LDAP认证')
    server_host = models.CharField(max_length=255, null=True, verbose_name='LDAP服务器地址')
    server_port = models.IntegerField(default=389, verbose_name='LDAP服务器端口')
    use_ssl = models.BooleanField(default=False, verbose_name='使用SSL/TLS')
    base_dn = models.CharField(max_length=255, null=True, verbose_name='Base DN')
    bind_dn = models.CharField(max_length=255, null=True, blank=True, verbose_name='绑定DN', help_text='管理员DN，用于搜索用户')
    bind_password = models.CharField(max_length=255, null=True, blank=True, verbose_name='绑定密码')
    user_search_filter = models.CharField(max_length=255, default='(uid={username})', verbose_name='用户搜索过滤器')
    user_attr_map = models.JSONField(default=dict, verbose_name='用户属性映射', help_text='LDAP属性到系统属性的映射')
    timeout = models.IntegerField(default=10, verbose_name='连接超时时间(秒)')
    update_time = models.DateTimeField(auto_now=True, null=True, verbose_name='更新时间')

    class Meta:
        db_table = 'ldap_config'
        verbose_name = 'LDAP配置'
        verbose_name_plural = verbose_name

    def __str__(self):
        return f"LDAP配置 - {self.server_host}:{self.server_port}"