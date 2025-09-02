<template>
  <div class="build-task-edit">
    <div class="page-header">
      <a-page-header
        :title="isEdit ? '编辑构建任务' : (isCopy ? '复制构建任务' : '新建构建任务')"
        @back="handleBack"
      />
    </div>

    <a-form
      :model="formState"
      :rules="rules"
      ref="formRef"
      layout="vertical"
    >
      <a-card title="基本信息" class="card-wrapper">
        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item label="任务名称" name="name" required>
              <a-input v-model:value="formState.name" placeholder="请输入任务名称" />
              <div class="form-item-help">任务名称将作为 Jenkins Job 名称，不能包含特殊字符</div>
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="所属项目" name="project_id" required>
              <a-select
                v-model:value="formState.project_id"
                placeholder="请选择项目"
                :options="projectOptions"
                @change="handleProjectChange"
                show-search
                :filter-option="filterOption"
              />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="构建环境" name="environment_id" required>
              <a-select
                v-model:value="formState.environment_id"
                placeholder="请选择环境"
                :options="environmentOptions"
                show-search
                :filter-option="filterOption"
              />
            </a-form-item>
          </a-col>
          <a-col :span="24">
            <a-form-item label="描述" name="description">
              <a-textarea
                v-model:value="formState.description"
                placeholder="请输入任务描述"
                :rows="4"
              />
            </a-form-item>
          </a-col>
        </a-row>
      </a-card>

      <a-card title="源码配置" class="card-wrapper">
        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item label="默认分支" name="branch">
              <a-input
                v-model:value="formState.branch"
                placeholder="可选：设置默认显示的分支，例如：main、master、develop"
              >
                <template #prefix>
                  <BranchesOutlined />
                </template>
              </a-input>
              <div class="form-item-help">设置构建时默认选中的分支，留空则默认选择仓库的默认分支。实际构建时将使用用户选择的分支进行构建。</div>
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="GitLab Token" name="git_token_id">
              <a-select
                v-model:value="formState.git_token_id"
                placeholder="请选择GitLab Token（GitLab仓库使用）"
                :loading="gitCredentialsLoading"
                :options="gitlabCredentials"
                show-search
                :filter-option="filterOption"
              >
                <template #suffixIcon>
                  <ReloadOutlined
                    :spin="gitCredentialsLoading"
                    @click="loadGitCredentials"
                  />
                </template>
              </a-select>
              <div class="form-item-help">
                用于访问GitLab仓库的Token凭证，如果没有合适的凭证，请先在凭证管理中添加
              </div>
            </a-form-item>
          </a-col>
        </a-row>
        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item label="GitHub Token" name="github_token_id">
              <a-select
                v-model:value="formState.github_token_id"
                placeholder="请选择GitHub Token（GitHub仓库使用）"
                :loading="gitCredentialsLoading"
                :options="githubCredentials"
                show-search
                :filter-option="filterOption"
              >
                <template #suffixIcon>
                  <ReloadOutlined
                    :spin="gitCredentialsLoading"
                    @click="loadGitCredentials"
                  />
                </template>
              </a-select>
              <div class="form-item-help">
                用于访问GitHub仓库的Token凭证，如果没有合适的凭证，请先在凭证管理中添加
              </div>
            </a-form-item>
          </a-col>
        </a-row>
      </a-card>

      <a-card class="card-wrapper">
        <template #title>
          <div class="card-title-with-action">
            <span>构建配置</span>
            <SystemVariablesList />
          </div>
        </template>

        <!-- 外部脚本库配置 -->
        <div class="external-script-config">
          <a-form-item>
            <a-checkbox v-model:checked="formState.use_external_script" @change="handleExternalScriptChange">
              <LinkOutlined style="color: #1890ff; margin-right: 4px;" />
              使用外部脚本库
            </a-checkbox>
            <div class="config-description">从Git仓库拉取构建和部署脚本，在Shell脚本中调用</div>
          </a-form-item>
          
          <div v-if="formState.use_external_script && formState.external_script_repo_url" class="external-script-summary">
            <a-descriptions size="small" :column="1" bordered>
              <a-descriptions-item label="仓库地址">
                <a-tooltip :title="formState.external_script_repo_url">
                  <LinkOutlined /> {{ truncateUrl(formState.external_script_repo_url) }}
                </a-tooltip>
              </a-descriptions-item>
              <a-descriptions-item label="存放目录">
                <FolderOutlined /> {{ formState.external_script_directory }}
              </a-descriptions-item>
              <a-descriptions-item v-if="formState.external_script_branch" label="分支">
                <BranchesOutlined /> {{ formState.external_script_branch }}
              </a-descriptions-item>
            </a-descriptions>
            <a-button type="link" size="small" @click="openExternalScriptModal">
              <EditOutlined /> 修改配置
            </a-button>
          </div>
        </div>

        <!-- 构建参数配置 -->
        <a-divider>构建参数</a-divider>
        <div class="parameters-list">
          <div v-for="(param, index) in formState.parameters" :key="index" class="parameter-item">
            <div class="parameter-header">
              <span class="parameter-number">
                <TagOutlined /> 参数 {{ index + 1 }}
              </span>
              <a-space>
                <a-tooltip title="删除">
                  <a-button
                    v-if="formState.parameters.length > 0"
                    type="text"
                    danger
                    @click="removeParameter(index)"
                  >
                    <DeleteOutlined />
                  </a-button>
                </a-tooltip>
              </a-space>
            </div>
            <a-row :gutter="16">
              <a-col :span="8">
                <a-form-item
                  label="参数名称"
                  :name="['parameters', index, 'name']"
                  :rules="[
                    { required: true, message: '请输入参数名称' },
                    { pattern: /^[A-Z_][A-Z0-9_]*$/, message: '参数名只能包含大写字母、数字和下划线，且必须以字母或下划线开头' }
                  ]"
                >
                  <a-input v-model:value="param.name" placeholder="例如：MY_SERVICES">
                    <template #prefix>
                      <KeyOutlined />
                    </template>
                  </a-input>
                  <div class="form-item-help">参数名只能包含大写字母、数字和下划线</div>
                </a-form-item>
              </a-col>
              <a-col :span="8">
                <a-form-item label="参数描述">
                  <a-input v-model:value="param.description" placeholder="参数用途说明" />
                </a-form-item>
              </a-col>
              <a-col :span="8">
                <a-form-item label="默认值">
                  <a-input v-model:value="param.defaultValuesText" placeholder="多个值用逗号分隔" @blur="updateDefaultValues(param, index)" />
                  <div class="form-item-help">多个默认值用英文逗号分隔</div>
                </a-form-item>
              </a-col>
            </a-row>
            <a-row :gutter="16">
              <a-col :span="24">
                <a-form-item
                  label="可选值"
                  :name="['parameters', index, 'choicesText']"
                  :rules="[{ required: true, message: '请输入可选值' }]"
                >
                  <a-textarea 
                    v-model:value="param.choicesText"
                    placeholder="每行一个选项值，例如：&#10;user-service&#10;payment-service"
                    :rows="3"
                    @blur="updateChoices(param, index)"
                  />
                  <div class="form-item-help">每行输入一个选项值</div>
                </a-form-item>
              </a-col>
            </a-row>
          </div>
        </div>

        <div class="parameter-actions">
          <a-button type="dashed" block @click="addParameter">
            <PlusOutlined /> 添加构建参数
          </a-button>
        </div>

        <a-divider>自动构建配置</a-divider>
        <div class="auto-build-config">
          <a-form-item>
            <a-checkbox v-model:checked="formState.auto_build_enabled" @change="handleAutoBuildChange">
              <ThunderboltOutlined style="color: #52c41a; margin-right: 4px;" />
              启用自动构建
            </a-checkbox>
            <div class="config-description">当代码推送到配置的分支时，自动触发构建任务</div>
          </a-form-item>
          
          <div v-if="formState.auto_build_enabled" class="auto-build-details">
                         <a-form-item label="自动构建分支" required>
               <a-select
                 v-model:value="formState.auto_build_branches"
                 mode="tags"
                 placeholder="输入分支名称，如：main, develop, release-v1.0"
                 style="width: 100%"
                 :token-separators="[',', ' ']"
               >
                 <a-select-option value="main">main</a-select-option>
                 <a-select-option value="master">master</a-select-option>
                 <a-select-option value="develop">develop</a-select-option>
               </a-select>
               <div class="form-item-help">请输入精确的分支名称，多个分支用逗号或空格分隔</div>
             </a-form-item>

            <a-form-item label="Webhook URL">
              <a-input
                :value="webhookUrl"
                readonly
                :addonBefore="'POST'"
              >
                <template #suffix>
                  <a-tooltip title="复制Webhook URL">
                    <a-button type="text" size="small" @click="copyWebhookUrl">
                      <CopyOutlined />
                    </a-button>
                  </a-tooltip>
                </template>
              </a-input>
              <div class="form-item-help">将此URL配置到GitLab项目的Webhook中，触发事件选择"Push events"</div>
            </a-form-item>

            <a-alert
              message="自动构建说明"
              description="启用自动构建后，当有代码推送到配置的分支时，系统将自动触发构建。构建参数将使用默认值，构建需求描述将自动获取最新提交信息。"
              type="info"
              show-icon
              style="margin-top: 16px;"
            />
          </div>
        </div>

        <a-divider>构建阶段</a-divider>
        <div class="stages-list">
          <div v-for="(stage, index) in formState.stages" :key="index" class="stage-item">
            <div class="stage-header">
              <span class="stage-number">
                <BuildOutlined /> 阶段 {{ index + 1 }}
              </span>
              <a-space>
                <a-tooltip title="上移">
                  <a-button
                    v-if="index > 0"
                    type="text"
                    @click="moveStage(index, 'up')"
                    :disabled="index === 0"
                  >
                    <UpOutlined />
                  </a-button>
                </a-tooltip>
                <a-tooltip title="下移">
                  <a-button
                    v-if="index < formState.stages.length - 1"
                    type="text"
                    @click="moveStage(index, 'down')"
                  >
                    <DownOutlined />
                  </a-button>
                </a-tooltip>
                <a-tooltip title="删除">
                  <a-button
                    v-if="formState.stages.length > 1"
                    type="text"
                    danger
                    @click="removeStage(index)"
                  >
                    <DeleteOutlined />
                  </a-button>
                </a-tooltip>
              </a-space>
            </div>
            <a-row :gutter="16">
              <a-col :span="8">
                <a-form-item
                  :name="['stages', index, 'name']"
                  :rules="[{ required: true, message: '请输入阶段名称' }]"
                >
                  <a-input v-model:value="stage.name" placeholder="阶段名称">
                    <template #prefix>
                      <TagOutlined />
                    </template>
                  </a-input>
                </a-form-item>
              </a-col>
              <a-col :span="16">
                <a-form-item
                  :name="['stages', index, 'script']"
                  :rules="[{ required: true, message: '请输入执行脚本' }]"
                >
                  <CodeEditor
                    v-model="stage.script"
                    :title="`Shell Script - ${stage.name || '未命名阶段'}`"
                    :placeholder="getShellScriptPlaceholder()"
                    :max-height="400"
                  />
                </a-form-item>
              </a-col>
            </a-row>
          </div>
        </div>

        <div class="stage-actions">
          <a-button type="dashed" block @click="addStage">
            <PlusOutlined /> 添加构建阶段
          </a-button>
        </div>
      </a-card>

      <BuildNotification v-model="formState.notification_channels" />

      <div class="form-footer">
        <a-space>
          <a-button @click="handleBack">取消</a-button>
          <a-button type="primary" :loading="submitLoading" @click="handleSubmit">
            保存
          </a-button>
        </a-space>
      </div>
    </a-form>

    <a-modal
      v-model:open="externalScriptModalVisible"
      title="配置外部脚本库"
      width="600px"
      @ok="handleExternalScriptModalOk"
      @cancel="handleExternalScriptModalCancel"
      :maskClosable="false"
    >
      <a-form
        :model="externalScriptForm"
        :rules="externalScriptRules"
        ref="externalScriptFormRef"
        layout="vertical"
      >
        <a-form-item
          label="Git仓库地址"
          name="repo_url"
        >
          <a-input
            v-model:value="externalScriptForm.repo_url"
            placeholder="请输入Git仓库地址，例如：https://github.com/example/scripts.git"
          >
            <template #prefix>
              <LinkOutlined />
            </template>
          </a-input>
        </a-form-item>

        <a-form-item
          label="存放目录"
          name="directory"
        >
          <a-input
            v-model:value="externalScriptForm.directory"
            placeholder="例如：/data/scripts"
          >
            <template #prefix>
              <FolderOutlined />
            </template>
          </a-input>
        </a-form-item>

        <a-form-item
          label="分支名称"
          name="branch"
        >
          <a-input
            v-model:value="externalScriptForm.branch"
            placeholder="请输入分支名称，例如：main、master、develop"
          >
            <template #prefix>
              <BranchesOutlined />
            </template>
          </a-input>
        </a-form-item>

        <a-form-item
          label="Git Token（私有仓库）"
          name="token_id"
        >
          <a-select
            v-model:value="externalScriptForm.token_id"
            placeholder="如果是私有仓库，请选择Git Token凭证"
            :options="gitCredentials"
            allow-clear
            show-search
            :filter-option="filterOption"
          >
            <template #suffixIcon>
              <ReloadOutlined
                :spin="gitCredentialsLoading"
                @click="loadGitCredentials"
              />
            </template>
          </a-select>
        </a-form-item>

        <a-alert
          message="配置说明"
          description="外部脚本库将在构建时被克隆到指定的绝对路径目录中，你可以在Shell脚本中通过绝对路径调用这些脚本文件。例如：/data/scripts/deploy.sh"
          type="info"
          show-icon
          style="margin-top: 16px;"
        />
      </a-form>
    </a-modal>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, nextTick, computed } from 'vue';
import { useRouter, useRoute } from 'vue-router';
import { message } from 'ant-design-vue';
import {
  PlusOutlined,
  DeleteOutlined,
  ReloadOutlined,
  QuestionCircleOutlined,
  BuildOutlined,
  DeploymentUnitOutlined,
  BranchesOutlined,
  CodeOutlined,
  LinkOutlined,
  ClockCircleOutlined,
  FieldTimeOutlined,
  TagOutlined,
  UpOutlined,
  DownOutlined,
  ThunderboltOutlined,
  CopyOutlined,
  LockOutlined,
  FolderOutlined,
  InfoCircleOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  MailOutlined,
  KeyOutlined,
  EditOutlined,
} from '@ant-design/icons-vue';
import axios from 'axios';
import CodeEditor from './components/CodeEditor.vue';
import BuildNotification from './components/BuildNotification.vue';
import SystemVariablesList from './components/SystemVariablesList.vue';

const router = useRouter();
const route = useRoute();
const formRef = ref();
const isEdit = ref(false);
const isCopy = ref(false);
const submitLoading = ref(false);
const loading = ref(false);
const projectOptions = ref([]);
const environmentOptions = ref([]);
const gitCredentials = ref([]);
const gitlabCredentials = ref([]);
const githubCredentials = ref([]);
const gitCredentialsLoading = ref(false);

// 外部脚本仓库相关状态
const externalScriptModalVisible = ref(false);
const currentStageIndex = ref(-1);
const externalScriptFormRef = ref();

// 外部脚本仓库表单
const externalScriptForm = reactive({
  repo_url: '',
  directory: '',
  branch: '',
  token_id: undefined,
});

// 外部脚本仓库表单验证规则
const externalScriptRules = {
  repo_url: [
    { required: true, message: '请输入Git仓库地址', trigger: 'blur' }
  ],
  directory: [
    { required: true, message: '请输入存放目录', trigger: 'blur' },
    { pattern: /^\/[a-zA-Z0-9/_-]+$/, message: '请输入正确的绝对路径，必须以/开头，只能包含字母、数字、下划线、连字符和斜杠', trigger: 'blur' }
  ],
  branch: [
    { required: true, message: '请输入分支名称', trigger: 'blur' },
    { min: 1, max: 100, message: '分支名称长度应在 1-100 个字符之间', trigger: 'blur' }
  ]
};

// 表单状态
const formState = reactive({
  task_id: '',
  name: '',
  project_id: undefined,
  environment_id: undefined,
  description: '',
  branch: '',
  git_token_id: undefined,
  github_token_id: undefined,
  use_external_script: false,
  external_script_repo_url: '',
  external_script_directory: '',
  external_script_branch: '',
  external_script_token_id: undefined,
  stages: [
    {
      name: '构建',
      script: '',
    }
  ],
  parameters: [],
  notification_channels: [],
  // 自动构建配置
  auto_build_enabled: false,
  auto_build_branches: [],
  webhook_token: '',
});

// 表单校验规则
const rules = {
  name: [
    { required: true, message: '请输入任务名称', trigger: 'blur' },
    { min: 2, max: 50, message: '任务名称长度应在 2-50 个字符之间', trigger: 'blur' },
  ],
  project_id: [
    { required: true, message: '请选择项目', trigger: 'change' },
  ],
  environment_id: [
    { required: true, message: '请选择环境', trigger: 'change' },
  ],
  git_token_id: [
    { required: true, message: '请选择Git Token', trigger: 'change' },
  ],
};

// 加载项目列表
const loadProjects = async () => {
  try {
    const token = localStorage.getItem('token');
    const response = await axios.get('/api/projects/', {
      headers: { 'Authorization': token }
    });
    
    if (response.data.code === 200) {
      projectOptions.value = response.data.data.map(item => ({
        label: item.name,
        value: item.project_id
      }));
    }
  } catch (error) {
    console.error('Load projects error:', error);
    message.error('加载项目列表失败');
  }
};

// 加载环境列表
const loadEnvironments = async () => {
  try {
    const token = localStorage.getItem('token');
    const response = await axios.get('/api/environments/', {
      headers: { 'Authorization': token }
    });
    
    if (response.data.code === 200) {
      environmentOptions.value = response.data.data.map(item => ({
        label: item.name,
        value: item.environment_id
      }));
    }
  } catch (error) {
    console.error('Load environments error:', error);
    message.error('加载环境列表失败');
  }
};

// 加载Git凭证列表（包括GitLab和GitHub）
const loadGitCredentials = async () => {
  try {
    gitCredentialsLoading.value = true;
    const token = localStorage.getItem('token');
    
    // 并行加载GitLab和GitHub凭证
    const [gitlabResponse, githubResponse] = await Promise.all([
      axios.get('/api/credentials/', {
        params: { type: 'gitlab_token' },
        headers: { 'Authorization': token }
      }),
      axios.get('/api/credentials/', {
        params: { type: 'github_token' },
        headers: { 'Authorization': token }
      })
    ]);
    
    // 处理GitLab凭证
    if (gitlabResponse.data.code === 200) {
      gitlabCredentials.value = gitlabResponse.data.data.map(item => ({
        label: item.name,
        value: item.credential_id,
        description: item.description
      }));
    }
    
    // 处理GitHub凭证
    if (githubResponse.data.code === 200) {
      githubCredentials.value = githubResponse.data.data.map(item => ({
        label: item.name,
        value: item.credential_id,
        description: item.description
      }));
    }
  } catch (error) {
    console.error('加载Git凭证失败:', error);
    message.error('加载Git凭证失败');
  } finally {
    gitCredentialsLoading.value = false;
  }
};

// 处理项目变更
const handleProjectChange = async (value) => {
  const project = projectOptions.value.find(item => item.value === value);
  if (project) {
    // 根据项目信息加载其他相关数据
  }
};

// 添加构建阶段
const addStage = () => {
  formState.stages.push({
    name: '',
    script: '',
  });
};

const removeStage = (index) => {
  formState.stages.splice(index, 1);
};

// 添加构建参数
const addParameter = () => {
  formState.parameters.push({
    name: '',
    description: '',
    choices: [],
    choicesText: '',
    choiceOptions: [],
    default_values: [],
    defaultValuesText: '',
  });
};

const removeParameter = (index) => {
  formState.parameters.splice(index, 1);
};

// 更新选项
const updateChoices = (param, index) => {
  if (param.choicesText) {
    const choices = param.choicesText.split('\n').filter(line => line.trim()).map(line => line.trim());
    param.choices = choices;
    param.choiceOptions = choices.map(choice => ({
      label: choice,
      value: choice
    }));
    
    param.default_values = param.default_values.filter(value => choices.includes(value));
  } else {
    param.choices = [];
    param.choiceOptions = [];
    param.default_values = [];
  }
};

// 更新默认值
const updateDefaultValues = (param, index) => {
  if (param.defaultValuesText) {
    const values = param.defaultValuesText.split(',').filter(val => val.trim()).map(val => val.trim());
    param.default_values = values;
  } else {
    param.default_values = [];
  }
};

// 处理返回
const handleBack = () => {
  router.back();
};

// 处理提交
const handleSubmit = async () => {
  try {
    await formRef.value.validate();
    submitLoading.value = true;
    
    const token = localStorage.getItem('token');
    const method = isEdit.value ? 'put' : 'post';
    
    // 构建提交数据
    const submitData = { ...formState };
    
    // 处理参数数据
    submitData.parameters = formState.parameters.map(param => ({
      name: param.name,
      description: param.description,
      choices: param.choices,
      default_values: param.default_values
    }));
    
    if (!submitData.use_external_script) {
      submitData.external_script_repo_url = '';
      submitData.external_script_directory = '';
      submitData.external_script_branch = '';
      submitData.external_script_token_id = undefined;
    }
    
    if (!isEdit.value || isCopy.value) {
      delete submitData.task_id;
    }
    
    const response = await axios[method]('/api/build/tasks/', submitData, {
      headers: { 'Authorization': token }
    });

    if (response.data.code === 200) {
      let successMsg = '创建构建任务成功';
      if (isEdit.value) {
        successMsg = '更新构建任务成功';
      } else if (isCopy.value) {
        successMsg = '复制构建任务成功';
      }
      message.success(successMsg);
      router.push('/build/tasks');
    } else {
      throw new Error(response.data.message);
    }
  } catch (error) {
    console.error('Submit task error:', error);
    let errorMsg = '创建构建任务失败';
    if (isEdit.value) {
      errorMsg = '更新构建任务失败';
    } else if (isCopy.value) {
      errorMsg = '复制构建任务失败';
    }
    message.error(error.message || errorMsg);
  } finally {
    submitLoading.value = false;
  }
};

// 加载任务详情
const loadTaskDetail = async (taskId) => {
  try {
    loading.value = true;
    const token = localStorage.getItem('token');
    const response = await axios.get(`/api/build/tasks/${taskId}`, {
      headers: { 'Authorization': token }
    });
    
    if (response.data.code === 200) {
      formState.task_id = response.data.data.task_id;
      formState.name = response.data.data.name;
      formState.description = response.data.data.description;
      formState.branch = response.data.data.branch;
      
      // 外部脚本库配置
      formState.use_external_script = response.data.data.use_external_script || false;
      formState.external_script_repo_url = response.data.data.external_script_repo_url || '';
      formState.external_script_directory = response.data.data.external_script_directory || '';
      formState.external_script_branch = response.data.data.external_script_branch || '';
      formState.external_script_token_id = response.data.data.external_script_token_id || undefined;
      
      const stages = response.data.data.stages || [];
      formState.stages = stages.map(stage => ({
        name: stage.name || '',
        script: stage.script || '',
      }));
      
      if (formState.stages.length === 0) {
        formState.stages.push({
          name: '构建',
          script: '',
        });
      }

      // 加载参数配置
      const parameters = response.data.data.parameters || [];
      formState.parameters = parameters.map(param => {
        const choicesText = (param.choices || []).join('\n');
        const defaultValuesText = (param.default_values || []).join(',');
        return {
          name: param.name || '',
          description: param.description || '',
          choices: param.choices || [],
          choicesText: choicesText,
          choiceOptions: (param.choices || []).map(choice => ({
            label: choice,
            value: choice
          })),
          default_values: param.default_values || [],
          defaultValuesText: defaultValuesText,
        };
      });
      
      formState.notification_channels = response.data.data.notification_channels || [];
      
      // 自动构建配置
      formState.auto_build_enabled = response.data.data.auto_build_enabled || false;
      formState.auto_build_branches = response.data.data.auto_build_branches || [];
      formState.webhook_token = response.data.data.webhook_token || '';
      
      if (response.data.data.project) {
        formState.project_id = response.data.data.project.project_id;
      }
      if (response.data.data.environment) {
        formState.environment_id = response.data.data.environment.environment_id;
      }
      if (response.data.data.git_token) {
        formState.git_token_id = response.data.data.git_token.credential_id;
      }
      if (response.data.data.github_token) {
        formState.github_token_id = response.data.data.github_token.credential_id;
      }

      // 加载相关选项数据
      await Promise.all([
        loadProjects(),
        loadEnvironments(),
        loadGitCredentials()
      ]);
    } else {
      message.error(response.data.message || '加载任务详情失败');
    }
  } catch (error) {
    console.error('加载任务详情失败:', error);
    message.error('加载任务详情失败');
  } finally {
    loading.value = false;
  }
};

// 复制任务加载任务详情
const loadTaskDetailForCopy = async (sourceTaskId) => {
  try {
    loading.value = true;
    const token = localStorage.getItem('token');
    const response = await axios.get(`/api/build/tasks/${sourceTaskId}`, {
      headers: { 'Authorization': token }
    });
    
    if (response.data.code === 200) {
      // 新任务不设置task_id
      formState.task_id = '';
      formState.name = response.data.data.name + ' - Copy';
      formState.description = response.data.data.description;
      formState.branch = response.data.data.branch;
      
      // 外部脚本库配置
      formState.use_external_script = response.data.data.use_external_script || false;
      formState.external_script_repo_url = response.data.data.external_script_repo_url || '';
      formState.external_script_directory = response.data.data.external_script_directory || '';
      formState.external_script_branch = response.data.data.external_script_branch || '';
      formState.external_script_token_id = response.data.data.external_script_token_id || undefined;
      
      const stages = response.data.data.stages || [];
      formState.stages = stages.map(stage => ({
        name: stage.name || '',
        script: stage.script || '',
      }));
      
      if (formState.stages.length === 0) {
        formState.stages.push({
          name: '构建',
          script: '',
        });
      }

      // 加载参数配置
      const parameters = response.data.data.parameters || [];
      formState.parameters = parameters.map(param => {
        const choicesText = (param.choices || []).join('\n');
        const defaultValuesText = (param.default_values || []).join(',');
        return {
          name: param.name || '',
          description: param.description || '',
          choices: param.choices || [],
          choicesText: choicesText,
          choiceOptions: (param.choices || []).map(choice => ({
            label: choice,
            value: choice
          })),
          default_values: param.default_values || [],
          defaultValuesText: defaultValuesText,
        };
      });
      
      formState.notification_channels = response.data.data.notification_channels || [];
      
      // 自动构建配置（复制时不复制webhook_token，会重新生成）
      formState.auto_build_enabled = response.data.data.auto_build_enabled || false;
      formState.auto_build_branches = response.data.data.auto_build_branches || [];
      formState.webhook_token = ''; // 复制时重置webhook token
      
      if (response.data.data.project) {
        formState.project_id = response.data.data.project.project_id;
      }
      if (response.data.data.environment) {
        formState.environment_id = response.data.data.environment.environment_id;
      }
      if (response.data.data.git_token) {
        formState.git_token_id = response.data.data.git_token.credential_id;
      }
      if (response.data.data.github_token) {
        formState.github_token_id = response.data.data.github_token.credential_id;
      }

      // 加载相关选项数据
      await Promise.all([
        loadProjects(),
        loadEnvironments(),
        loadGitCredentials()
      ]);
    } else {
      message.error(response.data.message || '加载任务详情失败');
    }
  } catch (error) {
    console.error('加载任务详情失败:', error);
    message.error('加载任务详情失败');
  } finally {
    loading.value = false;
  }
};

// 过滤选项方法
const filterOption = (input, option) => {
  return (
    option.label.toLowerCase().indexOf(input.toLowerCase()) >= 0 ||
    option.description?.toLowerCase().indexOf(input.toLowerCase()) >= 0
  );
};

const moveStage = (index, direction) => {
  const stages = formState.stages;
  if (direction === 'up' && index > 0) {
    [stages[index], stages[index - 1]] = [stages[index - 1], stages[index]];
  } else if (direction === 'down' && index < stages.length - 1) {
    [stages[index], stages[index + 1]] = [stages[index + 1], stages[index]];
  }
};

// 获取Shell脚本占位符
const getShellScriptPlaceholder = () => {
  let placeholder = `#!/bin/bash
# 在这里输入shell脚本
# 支持所有shell命令和Jenkins环境变量
# 例如：
# echo $JOB_NAME
# echo $BUILD_NUMBER
# echo $WORKSPACE`;

  if (formState.use_external_script && formState.external_script_directory) {
    placeholder += `\n\n# 调用外部脚本库中的脚本示例：\n# ${formState.external_script_directory}/deploy.sh\n# ${formState.external_script_directory}/build.sh`;
  }

  return placeholder;
};

// 处理外部脚本库变更
const handleExternalScriptChange = (checked) => {
  if (!checked) {
    // 取消使用外部脚本，清空相关配置
    formState.external_script_repo_url = '';
    formState.external_script_directory = '';
    formState.external_script_branch = '';
    formState.external_script_token_id = undefined;
  } else if (!formState.external_script_repo_url) {
    openExternalScriptModal();
  }
};

// 打开外部脚本库配置Modal
const openExternalScriptModal = () => {
  // 填充表单数据
  externalScriptForm.repo_url = formState.external_script_repo_url || '';
  externalScriptForm.directory = formState.external_script_directory || '';
  externalScriptForm.branch = formState.external_script_branch || '';
  externalScriptForm.token_id = formState.external_script_token_id || undefined;
  
  externalScriptModalVisible.value = true;
};

const handleExternalScriptModalOk = async () => {
  try {
    await externalScriptFormRef.value.validate();
    
    // 保存配置到formState
    formState.external_script_repo_url = externalScriptForm.repo_url;
    formState.external_script_directory = externalScriptForm.directory;
    formState.external_script_branch = externalScriptForm.branch;
    formState.external_script_token_id = externalScriptForm.token_id;
    
    externalScriptModalVisible.value = false;
    message.success('外部脚本库配置成功');
  } catch (error) {
    console.error('External script form validation failed:', error);
  }
};

// 处理外部脚本库Modal取消
const handleExternalScriptModalCancel = () => {
  if (!formState.external_script_repo_url) {
    formState.use_external_script = false;
  }
  externalScriptModalVisible.value = false;
};

// 截断URL显示
const truncateUrl = (url) => {
  if (!url) return '';
  return url.length > 50 ? url.substring(0, 47) + '...' : url;
};

// Webhook URL
const webhookUrl = computed(() => {
  if (!formState.task_id && !isEdit.value) {
    return '保存任务后将生成Webhook URL';
  }
  const taskId = formState.task_id || 'TASK_ID';
  const token = formState.webhook_token || 'WEBHOOK_TOKEN';
  const baseUrl = window.location.origin.replace(':5173', ':8900'); // 开发环境端口映射
  return `${baseUrl}/api/webhook/gitlab/${taskId}/?token=${token}`;
});

// 处理自动构建配置变更
const handleAutoBuildChange = (checked) => {
  if (checked && !formState.webhook_token) {
    // 生成webhook token
    formState.webhook_token = Math.random().toString(36).substring(2, 15) + Math.random().toString(36).substring(2, 15);
  }
  if (!checked) {
    // 取消自动构建时清除所有相关配置
    formState.auto_build_branches = [];
    formState.webhook_token = '';
  }
};

// 复制Webhook URL
const copyWebhookUrl = async () => {
  try {
    await navigator.clipboard.writeText(webhookUrl.value);
    message.success('Webhook URL已复制到剪贴板');
  } catch (error) {
    console.error('复制失败:', error);
    message.error('复制失败，请手动复制');
  }
};

onMounted(async () => {
  const taskId = route.query.task_id;
  const sourceTaskId = route.query.source_task_id;
  
  if (taskId) {
    isEdit.value = true;
    await loadTaskDetail(taskId);
  } else if (sourceTaskId) {
    isCopy.value = true;
    await loadTaskDetailForCopy(sourceTaskId);
  } else {
    loadProjects();
    loadEnvironments();
    loadGitCredentials();
  }
});
</script>

<style scoped>
.page-header {
  margin-bottom: 24px;
  background: #fff;
  border-radius: 4px;
}

:deep(.ant-page-header) {
  padding: 16px 24px;
}

.card-wrapper {
  margin-bottom: 24px;
  border-radius: 4px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
}

:deep(.ant-card-head) {
  border-bottom: 1px solid #f0f0f0;
  padding: 0 24px;
}

:deep(.ant-card-head-title) {
  font-size: 16px;
  font-weight: 500;
}

:deep(.ant-card-body) {
  padding: 24px;
}

.form-item-help {
  font-size: 12px;
  color: rgba(0, 0, 0, 0.45);
  margin-top: 4px;
}

.stages-list {
  margin-top: 16px;
}

.stage-item {
  padding: 16px;
  background: transparent;
  border-radius: 4px;
  margin-bottom: 16px;
  border: 1px solid #e8e8e8;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
}

.stage-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  padding-bottom: 8px;
  border-bottom: 1px solid #e8e8e8;
}

.stage-number {
  font-size: 14px;
  font-weight: 500;
  color: rgba(0, 0, 0, 0.85);
}

.stage-actions {
  margin-top: 16px;
}

.parameters-list {
  margin-top: 16px;
}

.parameter-item {
  padding: 16px;
  background: transparent;
  border-radius: 4px;
  margin-bottom: 16px;
  border: 1px solid #e8e8e8;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
}

.parameter-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  padding-bottom: 8px;
  border-bottom: 1px solid #e8e8e8;
}

.parameter-number {
  font-size: 14px;
  font-weight: 500;
  color: rgba(0, 0, 0, 0.85);
}

.parameter-actions {
  margin-top: 16px;
}

.form-footer {
  margin-top: 24px;
  text-align: center;
  background: #fff;
  padding: 16px;
  border-radius: 4px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}

:deep(.ant-radio-button-wrapper) {
  margin-right: 8px;
}

:deep(.ant-checkbox-group) {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

:deep(.ant-form-item-label) {
  font-weight: 500;
}

ul {
  margin: 0;
  padding-left: 16px;
}

li {
  color: rgba(0, 0, 0, 0.45);
}

.channel-icon {
  width: 16px;
  height: 16px;
  vertical-align: -0.125em;
}

.notification-template-vars {
  margin-top: 8px;
  padding: 8px;
  background-color: transparent;
  border-radius: 4px;
  border: 1px solid #e8e8e8;
}

.card-title-with-action {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
}

.external-script-config {
  margin-bottom: 24px;
  padding: 16px;
  border: 1px solid #e8e8e8;
  border-radius: 6px;
  background-color: transparent;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
}

.config-description {
  font-size: 12px;
  color: rgba(0, 0, 0, 0.45);
  margin-top: 4px;
  margin-left: 24px;
}

.external-script-summary {
  margin-top: 12px;
  padding: 12px;
  background-color: transparent;
  border-radius: 4px;
  border: 1px solid #e8e8e8;
}

.external-script-summary :deep(.ant-descriptions-item-label) {
  font-weight: 500;
  color: #595959;
  width: 100px;
}

.external-script-summary :deep(.ant-descriptions-item-content) {
  color: #262626;
}

.auto-build-config {
  margin-bottom: 24px;
  padding: 16px;
  border: 1px solid #e8e8e8;
  border-radius: 6px;
  background-color: transparent;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
}

.auto-build-details {
  margin-top: 12px;
  padding: 12px;
  background-color: transparent;
  border-radius: 4px;
  border: 1px solid #e8e8e8;
}
</style>