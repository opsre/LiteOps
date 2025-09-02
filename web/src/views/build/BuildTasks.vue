<template>
  <div class="build-tasks">
    <div class="page-header">
      <a-row justify="space-between" align="middle">
        <a-col>
          <h2>构建任务</h2>
        </a-col>
        <a-col>
          <a-space>
            <a-button type="primary" @click="handleCreateTask">
              <template #icon><PlusOutlined /></template>
              新建构建任务
            </a-button>
          </a-space>
        </a-col>
      </a-row>
    </div>

    <a-card>
      <!-- 搜索区域 -->
      <div class="search-area">
        <a-form layout="inline" :style="{ marginBottom: '16px', display: 'flex', justifyContent: 'flex-end' }">
          <a-form-item label="项目">
            <a-select
              v-model:value="searchForm.project_id"
              style="width: 200px"
              placeholder="选择项目"
              @change="handleProjectChange"
            >
              <a-select-option value="all">全部项目</a-select-option>
              <a-select-option
                v-for="project in projectOptions"
                :key="project.project_id"
                :value="project.project_id"
              >
                {{ project.name }}
              </a-select-option>
            </a-select>
          </a-form-item>
          <a-form-item label="环境">
            <a-select
              v-model:value="searchForm.environment_id"
              style="width: 200px"
              placeholder="选择环境"
              @change="handleEnvironmentChange"
            >
              <a-select-option value="all">全部环境</a-select-option>
              <a-select-option
                v-for="env in environmentOptions"
                :key="env.environment_id"
                :value="env.environment_id"
              >
                {{ env.name }}
              </a-select-option>
            </a-select>
          </a-form-item>
          <a-form-item label="任务名称">
            <a-input
              v-model:value="searchForm.name"
              placeholder="请输入任务名称"
              allow-clear
              @pressEnter="handleSearch"
            >
              <template #prefix>
                <SearchOutlined style="color: rgba(0, 0, 0, 0.25)" />
              </template>
            </a-input>
          </a-form-item>
          <a-form-item>
            <a-button type="primary" :loading="loading" @click="handleSearch">
              <template #icon><SearchOutlined /></template>
              搜索
            </a-button>
          </a-form-item>
        </a-form>
      </div>

      <!-- 任务列表 -->
      <a-table
        :columns="columns"
        :data-source="buildTasks"
        :loading="loading"
        row-key="task_id"
      >
        <template #bodyCell="{ column, record }">
          <!-- 任务名称列 -->
          <template v-if="column.key === 'name'">
            <a @click="handleViewTask(record)" style="color: rgba(0, 0, 0, 0.85)">{{ record.name }}</a>
          </template>

          <!-- 状态列 - 显示任务状态或构建状态 -->
          <template v-if="column.key === 'status'">
            <div class="task-status">
              <a-tag v-if="record.building_status === 'building'" color="#1677ff" class="building-tag">
                <LoadingOutlined class="spinning" />
                构建中
              </a-tag>
              <a-tag v-else :color="getTaskStatusHexColor(record.status)" class="task-status-tag">
                {{ getTaskStatusText(record.status) }}
              </a-tag>
            </div>
          </template>

          <!-- 构建统计列 -->
          <template v-if="column.key === 'statistics'">
            <div class="build-statistics">
              <div class="statistics-row">
                <a-tooltip title="总构建次数">
                  <span class="stat-item total">
                    <BuildOutlined class="stat-icon" />
                    {{ record.total_builds }}
                  </span>
                </a-tooltip>
                <a-tooltip title="成功次数">
                  <span class="stat-item success">
                    <CheckCircleOutlined class="stat-icon" style="color: #74CF47;"/>
                    {{ record.success_builds }}
                  </span>
                </a-tooltip>
                <a-tooltip title="失败次数">
                  <span class="stat-item failed">
                    <CloseCircleOutlined class="stat-icon" style="color: #FF7072;"/>
                    {{ record.failure_builds }}
                  </span>
                </a-tooltip>
              </div>
            </div>
          </template>

          <!-- 最近构建列 -->
          <template v-if="column.key === 'last_build'">
            <div v-if="record.last_build" class="last-build-info">
              <div class="build-number-status">
                <a-tooltip title="点击查看该任务的构建历史" placement="top">
                  <a @click="handleViewBuildDetail(record)" class="build-number-link">
                    <span class="build-number">#{{ record.last_build.number }}</span>
                  </a>
                </a-tooltip>
                <a-tag 
                  :color="getBuildStatusHexColor(record.last_build.status)"
                  class="build-status-tag"
                >
                  {{ getBuildStatusText(record.last_build.status) }}
                </a-tag>
              </div>
              <div class="build-details">
                <div class="build-time">
                  <ClockCircleOutlined class="icon" />
                  {{ formatBuildTime(record.last_build.time) }}
                </div>
                <div class="build-duration">
                  <FieldTimeOutlined class="icon" />
                  {{ record.last_build.duration }}
                </div>
              </div>
            </div>
            <div v-else class="no-build">
              <span class="no-build-text">暂无构建记录</span>
            </div>
          </template>

          <!-- 操作列 -->
          <template v-if="column.key === 'action'">
            <a-space>
              <a-button
                type="primary"
                size="small"
                :loading="record.building_status === 'building'"
                @click="handleBuild(record)"
                :disabled="record.status === 'disabled' || record.building_status === 'building'"
              >
                <template v-if="record.building_status === 'building'">构建中...</template>
                <template v-else>立即构建</template>
              </a-button>
              <a-button
                v-if="record.building_status === 'building'"
                type="primary"
                danger
                size="small"
                @click="handleStopBuild(record)"
              >
                停止构建
              </a-button>
              <a-dropdown>
                <a-button size="small">
                  更多
                  <DownOutlined />
                </a-button>
                <template #overlay>
                  <a-menu>
                    <a-menu-item key="view-log" @click="handleViewLog(record)">
                      日志
                    </a-menu-item>
                    <a-menu-item key="edit" @click="handleEdit(record)">
                      编辑
                    </a-menu-item>
                    <a-menu-item key="copy" @click="handleCopy(record)">
                      复制
                    </a-menu-item>
                    <a-menu-divider />
                    <a-menu-item
                      key="enable-disable"
                      @click="handleToggleStatus(record)"
                    >
                      <template v-if="record.status === 'disabled'">
                        启用
                      </template>
                      <template v-else>
                        禁用
                      </template>
                    </a-menu-item>
                    <a-menu-item key="delete" @click="handleDelete(record)">
                      删除
                    </a-menu-item>
                  </a-menu>
                </template>
              </a-dropdown>
            </a-space>
          </template>
        </template>
      </a-table>
    </a-card>

    <!-- 构建日志弹窗 -->
    <a-modal
      v-model:open="logModalVisible"
      title="构建日志"
      width="1000px"
      :footer="null"
      @cancel="handleLogModalClose"
      :maskClosable="false"
      :bodyStyle="{ padding: '0', height: 'auto', maxHeight: 'calc(100vh - 150px)', overflow: 'hidden' }"
    >
      <div class="log-content">
        <div class="log-viewer-container">
          <FullscreenLogViewer
            ref="logViewerRef"
            :logContent="buildLog"
            :autoScroll="autoScroll"
            title="构建日志"
          />
        </div>
        <div class="log-footer">
          <div class="log-controls">
            <div class="left-controls">
              <a-checkbox v-model:checked="autoScroll">自动滚动</a-checkbox>
            </div>
            <div class="right-controls">
              <a-space>
                <a-button 
                  v-if="selectedTask && selectedTask.building_status === 'building'"
                  type="primary" 
                  danger 
                  @click="handleStopBuildInLog"
                  :loading="stopBuildLoading"
                >
                  <template #icon><StopOutlined /></template>
                  停止构建
                </a-button>
                <a-button type="primary" @click="handleDownloadLog">
                  <template #icon><DownloadOutlined /></template>
                  下载日志
                </a-button>
                <a-button type="primary" danger @click="handleLogModalClose">
                  关闭
                </a-button>
              </a-space>
            </div>
          </div>
        </div>
      </div>
    </a-modal>

    <!-- 构建弹窗 -->
    <a-modal
      v-model:open="buildModalVisible"
      :title="buildModalTitle"
      @ok="confirmBuild"
      :confirmLoading="buildConfirmLoading"
      width="700px"
    >
      <a-form :model="buildForm" layout="vertical">
        <a-form-item label="选择分支" required v-if="isDevOrTestEnv">
          <a-select
            showSearch
            v-model:value="buildForm.branch"
            placeholder="请选择分支"
            :loading="branchLoading"
            @change="handleBranchChange"
            style="width: 100%"
          >
            <a-select-option
              v-for="branch in branchList"
              :key="branch.name"
              :value="branch.name"
            >
              <span>{{ branch.name }}</span>
              <span class="branch-commit-info">
                <a-tag size="small">{{ branch.commit.author_name }}</a-tag>
                {{ branch.commit.title }}
              </span>
            </a-select-option>
          </a-select>
        </a-form-item>

        <a-form-item label="提交记录" required v-if="isDevOrTestEnv">
          <a-spin :spinning="commitLoading">
            <div class="commit-list-wrapper">
              <a-list
                class="commit-list"
                :data-source="commitList"
                size="small"
                bordered
              >
                <template #renderItem="{ item }">
                  <a-list-item>
                    <div class="commit-item">
                      <div class="commit-title">
                        <span class="commit-id">{{ item.short_id }}</span>
                        {{ item.title }}
                      </div>
                      <div class="commit-meta">
                        <span class="commit-author">
                          <UserOutlined /> {{ item.author_name }}
                        </span>
                        <span class="commit-time">
                          <ClockCircleOutlined /> {{ item.created_at }}
                        </span>
                      </div>
                      <div class="commit-message" v-if="item.message">
                        {{ item.message }}
                      </div>
                    </div>
                  </a-list-item>
                </template>
              </a-list>
            </div>
          </a-spin>
        </a-form-item>

        <!-- 预发布和生产环境的构建方式选择 -->
        <a-form-item
          label="构建方式"
          required
          v-if="isStagingOrProdEnv"
        >
          <a-radio-group v-model:value="buildForm.buildType" @change="handleBuildTypeChange">
            <a-radio value="existing_version">现有版本</a-radio>
            <a-radio value="rebuild">重新构建</a-radio>
          </a-radio-group>
          <div class="build-type-description">
            <div v-if="buildForm.buildType === 'existing_version'" class="description-text">
              <InfoCircleOutlined style="margin-right: 4px; color: #1890ff;" />
              使用已在其它环境验证通过的版本进行部署，适用于可通过环境变量切换接口的项目
            </div>
            <div v-else class="description-text">
              <InfoCircleOutlined style="margin-right: 4px; color: #ff7875;" />
              重新从代码构建，适用于构建时需要指定不同环境接口配置的项目（如前端项目需要env指定）
            </div>
          </div>
        </a-form-item>

        <!-- 预发布和生产环境的版本选择 -->
        <a-form-item
          label="输入版本号"
          required
          v-if="isStagingOrProdEnv && buildForm.buildType === 'existing_version'"
          help="请输入已在其它环境验证通过的版本号，可以在构建历史中查看"
        >
          <a-input
            v-model:value="buildForm.version"
            placeholder="例如: 20250320112507_029e149e"
            allow-clear
          >
            <template #prefix>
              <TagOutlined style="color: rgba(0, 0, 0, 0.25)" />
            </template>
            <template #suffix>
              <a-tooltip title="版本号格式为: 年月日时分秒_提交ID前8位，可以在构建历史中找到">
                <QuestionCircleOutlined style="color: rgba(0, 0, 0, 0.45)" />
              </a-tooltip>
            </template>
          </a-input>
          <div class="version-tip">
            <InfoCircleOutlined style="margin-right: 4px; color: #1890ff;" />
            <span>提示: 可以去 <a @click="goToBuildHistory">构建历史</a> 页面查找其它环境最新的构建版本</span>
          </div>
        </a-form-item>

        <!-- 预发布和生产环境重新构建时的分支选择 -->
        <a-form-item label="选择分支" required v-if="isStagingOrProdEnv && buildForm.buildType === 'rebuild'">
          <a-select
            showSearch
            v-model:value="buildForm.branch"
            placeholder="请选择分支"
            :loading="branchLoading"
            @change="handleBranchChange"
            style="width: 100%"
          >
            <a-select-option
              v-for="branch in branchList"
              :key="branch.name"
              :value="branch.name"
            >
              <span>{{ branch.name }}</span>
              <span class="branch-commit-info">
                <a-tag size="small">{{ branch.commit.author_name }}</a-tag>
                {{ branch.commit.title }}
              </span>
            </a-select-option>
          </a-select>
        </a-form-item>

        <!-- 预发布和生产环境重新构建时的提交记录 -->
        <a-form-item label="提交记录" required v-if="isStagingOrProdEnv && buildForm.buildType === 'rebuild'">
          <a-spin :spinning="commitLoading">
            <div class="commit-list-wrapper">
              <a-list
                class="commit-list"
                :data-source="commitList"
                size="small"
                bordered
              >
                <template #renderItem="{ item }">
                  <a-list-item>
                    <div class="commit-item">
                      <div class="commit-title">
                        <span class="commit-id">{{ item.short_id }}</span>
                        {{ item.title }}
                      </div>
                      <div class="commit-meta">
                        <span class="commit-author">
                          <UserOutlined /> {{ item.author_name }}
                        </span>
                        <span class="commit-time">
                          <ClockCircleOutlined /> {{ item.created_at }}
                        </span>
                      </div>
                      <div class="commit-message" v-if="item.message">
                        {{ item.message }}
                      </div>
                    </div>
                  </a-list-item>
                </template>
              </a-list>
            </div>
          </a-spin>
        </a-form-item>

        <!-- 构建参数选择 -->
        <div v-if="selectedTask?.parameters?.length > 0" class="build-parameters">
          <a-divider>构建参数</a-divider>
          
          <div v-for="param in selectedTask.parameters" :key="param.name" class="parameter-group">
            <a-form-item :label="param.name">
              <a-checkbox-group 
                v-model:value="buildForm.parameterValues[param.name]" 
                :options="param.choiceOptions"
              />
              <div class="parameter-help" v-if="param.description">{{ param.description }}</div>
            </a-form-item>
          </div>
        </div>

        <a-form-item label="构建需求描述" required>
          <a-textarea
            v-model:value="buildForm.requirement"
            placeholder="请输入本次构建的需求描述，例如：修复了某个bug、新增了某个功能等"
            :rows="4"
            :maxLength="500"
            showCount
          />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onUnmounted, computed, nextTick } from 'vue';
import { message, Modal } from 'ant-design-vue';
import {
  PlusOutlined,
  SearchOutlined,
  DownOutlined,
  UserOutlined,
  ClockCircleOutlined,
  DownloadOutlined,
  TagOutlined,
  QuestionCircleOutlined,
  InfoCircleOutlined,
  BuildOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  StopOutlined,
  FieldTimeOutlined,
  LoadingOutlined,
  CopyOutlined
} from '@ant-design/icons-vue';
import { useRouter } from 'vue-router';
import axios from 'axios';
import FullscreenLogViewer from './components/FullscreenLogViewer.vue';
// import { hasFunctionPermission } from '../../utils/permission';
import { hasFunctionPermission, checkPermission } from '../../utils/permission';

// 初始化 router 实例
const router = useRouter();

// 状态变量
const loading = ref(false);
const buildTasks = ref([]);
const projectOptions = ref([]);
const environmentOptions = ref([]);
const logModalVisible = ref(false);
const autoScroll = ref(true);
const buildLog = ref('');
const logUpdateTimer = ref(null);

// 构建相关状态
const buildModalVisible = ref(false);
const buildConfirmLoading = ref(false);
const branchLoading = ref(false);
const commitLoading = ref(false);
const branchList = ref([]);
const commitList = ref([]);
const selectedTask = ref(null);
const selectedHistoryId = ref('');
const buildForm = reactive({
  branch: '',
  commit_id: '',
  requirement: '',
  version: '',
  buildType: 'existing_version',
  parameterValues: {},
});

// SSE相关状态
const eventSource = ref(null);
const logViewerRef = ref(null);
const stopBuildLoading = ref(false);

// 搜索表单
const searchForm = reactive({
  project_id: 'all',
  environment_id: 'all',
  name: '',
});

// 表格列定义
const columns = [
  {
    title: '任务名称',
    dataIndex: 'name',
    key: 'name',
  },
  {
    title: '所属项目',
    dataIndex: ['project', 'name'],
    key: 'project',
  },
  {
    title: '构建环境',
    dataIndex: ['environment', 'name'],
    key: 'environment',
  },
  {
    title: '默认分支',
    dataIndex: 'branch',
    key: 'branch',
  },
  {
    title: '任务状态',
    dataIndex: 'status',
    key: 'status',
  },
  {
    title: '最近构建',
    key: 'last_build',
  },
  {
    title: '构建统计',
    key: 'statistics',
  },
  {
    title: '创建者',
    dataIndex: ['creator', 'name'],
    key: 'creator',
  },
  {
    title: '创建时间',
    dataIndex: 'create_time',
    key: 'create_time',
  },
  {
    title: '操作',
    key: 'action',
    fixed: 'right',
  },
];

// 获取构建状态颜色
const getBuildStatusColor = (status) => {
  const colors = {
    created: 'rgba(22,119,255,0.8)',
    disabled: 'rgba(255, 77, 79,0.8)',
    running: 'processing',
    success: 'success',
    failed: 'error',
    building: 'rgba(22,119,255,0.8)',
    idle: 'default',
    terminated: 'rgba(128, 128, 128, 0.8)', // 灰色
    pending: 'warning'
  };
  return colors[status] || 'default';
};

// 获取构建状态文本
const getBuildStatusText = (status) => {
  const texts = {
    created: '正常',
    disabled: '禁用',
    running: '运行中',
    success: '成功',
    failed: '失败',
    building: '构建中',
    idle: '空闲',
    terminated: '已终止',
    pending: '等待中'
  };
  return texts[status] || status;
};

// 获取任务状态颜色
const getTaskStatusColor = (status) => {
  const colors = {
    created: 'success',
    disabled: 'error',
  };
  return colors[status] || 'default';
};

// 获取任务状态十六进制颜色
const getTaskStatusHexColor = (status) => {
  const colors = {
    created: '#74CF47',
    disabled: '#FF7072',
  };
  return colors[status] || '#d9d9d9';
};

// 获取任务状态文本
const getTaskStatusText = (status) => {
  const texts = {
    created: '正常',
    disabled: '已禁用',
  };
  return texts[status] || status;
};

// 获取构建状态十六进制颜色
const getBuildStatusHexColor = (status) => {
  const colors = {
    created: '#1677ff',
    disabled: '#FF7072',
    running: '#1677ff',
    success: '#74CF47',
    failed: '#FF7072',
    building: '#1677ff',
    idle: '#d9d9d9',
    terminated: '#8c8c8c',
    pending: '#faad14'
  };
  return colors[status] || '#d9d9d9';
};

// 格式化构建时间
const formatBuildTime = (time) => {
  if (!time) return '';
  const date = new Date(time);
  const now = new Date();
  const diff = now - date;
  
  // 小于1分钟显示"刚刚"
  if (diff < 60000) {
    return '刚刚';
  }
  
  // 小于1小时显示"X分钟前"
  if (diff < 3600000) {
    const minutes = Math.floor(diff / 60000);
    return `${minutes}分钟前`;
  }
  
  // 小于1天显示"X小时前"
  if (diff < 86400000) {
    const hours = Math.floor(diff / 3600000);
    return `${hours}小时前`;
  }
  
  // 小于30天显示"X天前"
  if (diff < 2592000000) {
    const days = Math.floor(diff / 86400000);
    return `${days}天前`;
  }
  
  // 超过30天显示具体日期
  return date.toLocaleDateString('zh-CN', {
    year: 'numeric',
    month: 'numeric',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  });
};

// 加载项目列表
const loadProjects = async () => {
  try {
    const token = localStorage.getItem('token');
    const response = await axios.get('/api/projects/', {
      headers: { 'Authorization': token }
    });

    if (response.data.code === 200) {
      projectOptions.value = response.data.data;
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
      environmentOptions.value = response.data.data;
    }
  } catch (error) {
    console.error('Load environments error:', error);
    message.error('加载环境列表失败');
  }
};

// 加载任务列表
const loadTasks = async () => {
  try {
    loading.value = true;
    const token = localStorage.getItem('token');
    const params = { ...searchForm };

    if (params.project_id === 'all') {
      delete params.project_id;
    }
    if (params.environment_id === 'all') {
      delete params.environment_id;
    }

    const response = await axios.get('/api/build/tasks/', {
      params,
      headers: { 'Authorization': token }
    });

    if (response.data.code === 200) {
      buildTasks.value = response.data.data;
    }
  } catch (error) {
    console.error('Load tasks error:', error);
    message.error('加载任务列表失败');
  } finally {
    loading.value = false;
  }
};

// 处理搜索
const handleSearch = () => {
  loadTasks();
};

// 处理创建任务
const handleCreateTask = () => {
  router.push('/build/tasks/create');
};

// 处理查看任务
const handleViewTask = (record) => {
  router.push({
    name: 'build-task-detail',
    query: { task_id: record.task_id }
  });
};

// 处理构建
const handleBuild = async (record) => {
  // 检查任务是否有正在进行的构建
  if (record.building_status === 'building') {
    message.warning('当前任务正在构建中，请等待构建完成后再试');
    return;
  }

  selectedTask.value = record;
  // 重置所有构建表单数据
  buildForm.branch = '';
  buildForm.commit_id = '';
  buildForm.requirement = '';
  buildForm.version = '';
  buildForm.buildType = 'existing_version';
  buildForm.parameterValues = {};

  // 初始化参数默认值
  if (record.parameters && record.parameters.length > 0) {
    record.parameters.forEach(param => {
      // 处理参数选项
      param.choiceOptions = (param.choices || []).map(choice => ({
        label: choice,
        value: choice
      }));
      
      // 设置默认值
      buildForm.parameterValues[param.name] = [...(param.default_values || [])];
    });
  }

  // 显示构建对话框
  buildModalVisible.value = true;

  if (isDevOrTestEnv.value) {
    await loadBranches();
  }
};

// 处理停止构建
const handleStopBuild = async (record) => {
  try {
    if (!record.last_build) {
      message.warning('没有找到正在进行的构建');
      return;
    }

    // 确认是否要停止构建
    Modal.confirm({
      title: '确认停止构建',
      content: `确定要停止任务 "${record.name}" 的构建吗？`,
      okText: '确定',
      okType: 'danger',
      cancelText: '取消',
      async onOk() {
        try {
          const token = localStorage.getItem('token');
          const response = await axios.put('/api/build/tasks/build', {
            history_id: record.last_build.id
          }, {
            headers: { 'Authorization': token }
          });

          if (response.data.code === 200) {
            message.success('已停止构建');
            // 刷新任务列表
            loadTasks();
          } else {
            message.error(response.data.message || '停止构建失败');
          }
        } catch (error) {
          console.error('Stop build error:', error);
          message.error('停止构建失败');
        }
      }
    });
  } catch (error) {
    console.error('Stop build error:', error);
    message.error('停止构建失败');
  }
};

// 停止日志更新
const stopLogUpdate = () => {
  if (logUpdateTimer.value) {
    clearInterval(logUpdateTimer.value);
    logUpdateTimer.value = null;
  }
};

// 处理查看日志
const handleViewLog = async (record) => {
  try {
    // 检查权限
    const module = 'build_task';
    const action = 'view_log';
    if (!hasFunctionPermission(module, action)) {
      message.error('你没有查看构建日志的权限');
      return;
    }

    selectedTask.value = record;

    if (!record.last_build) {
      message.warning('暂无构建历史');
      return;
    }

    selectedHistoryId.value = record.last_build.id;
    const token = localStorage.getItem('token');

    // 检查是否是正在进行的构建
    const isBuilding = record.building_status === 'building' && 
                      ['pending', 'running'].includes(record.last_build.status);

    if (isBuilding) {
      // 如果是正在进行的构建，使用SSE连接获取实时日志
      buildLog.value = '正在连接到构建日志流...\n';
      logModalVisible.value = true;

      // 连接SSE获取实时日志
      connectSSE(record.task_id, record.last_build.number);

      // 滚动到底部
      nextTick(() => {
        if (logViewerRef.value?.logBodyRef) {
          logViewerRef.value.scrollToBottom();
        }
      });
    } else {
      // 如果是已完成的构建，获取静态日志
      const logResponse = await axios.get(`/api/build/history/log/${selectedHistoryId.value}/`, {
        headers: { 'Authorization': token }
      });

      if (logResponse.data.code === 200) {
        buildLog.value = logResponse.data.data.log;
        logModalVisible.value = true;

        // 滚动到底部
        nextTick(() => {
          if (logViewerRef.value?.logBodyRef) {
            logViewerRef.value.scrollToBottom();
          }
        });
      }
    }
  } catch (error) {
    console.error('View log error:', error);
    message.error('获取日志失败');
  }
};

// 处理切换任务状态
const handleToggleStatus = async (record) => {
  try {
    // 检查权限
    const module = 'build_task';
    const action = 'disable';
    if (!hasFunctionPermission(module, action)) {
      message.error('你没有禁用/启用任务的权限');
      return;
    }

    const token = localStorage.getItem('token');
    const newStatus = record.status === 'disabled' ? 'created' : 'disabled';

    await axios.put('/api/build/tasks/', {
      task_id: record.task_id,
      status: newStatus
    }, {
      headers: { 'Authorization': token }
    });

    message.success(`${newStatus === 'disabled' ? '禁用' : '启用'}成功`);
    loadTasks();
  } catch (error) {
    console.error('Toggle status error:', error);
    message.error(`${record.status === 'disabled' ? '启用' : '禁用'}失败`);
  }
};

// 处理删除任务
const handleDelete = (record) => {
  Modal.confirm({
    title: '确认删除',
    content: `确定要删除构建任务"${record.name}"吗？`,
    okText: '确定',
    okType: 'danger',
    cancelText: '取消',
    async onOk() {
      try {
          // 检查功能权限和数据权限
        const module = 'build_task';
        const action = 'delete';
        if (!checkPermission(module, action, record.project?.project_id, 'project')) {
          return;
        }
        const token = localStorage.getItem('token');
        await axios.delete('/api/build/tasks/', {
          data: { task_id: record.task_id },
          headers: { 'Authorization': token }
        });

        message.success('删除成功');
        loadTasks();
      } catch (error) {
        console.error('Delete task error:', error);
        message.error('删除失败');
      }
    },
  });
};

// 处理项目变更
const handleProjectChange = () => {
  searchForm.environment_id = 'all';
  loadTasks();
};

// 处理环境变更
const handleEnvironmentChange = () => {
  loadTasks();
};

// 加载分支列表
const loadBranches = async () => {
  try {
    branchLoading.value = true;
    const token = localStorage.getItem('token');
    
    // 显示加载提示
    message.loading('正在加载分支列表...', 0);
    
    const response = await axios.get('/api/github/branches/', {
      params: { task_id: selectedTask.value.task_id },
      headers: { 'Authorization': token },
      timeout: 30000 // 30秒超时
    });

    // 关闭加载提示
    message.destroy();

    if (response.data.code === 200) {
      branchList.value = response.data.data;
      if (branchList.value.length > 0) {
        // 如果任务设置了默认分支且该分支存在，则选中它
        if (selectedTask.value.branch && branchList.value.find(b => b.name === selectedTask.value.branch)) {
          buildForm.branch = selectedTask.value.branch;
        } else {
          // 否则选择第一个分支
          buildForm.branch = branchList.value[0].name;
        }
        await handleBranchChange(buildForm.branch);
      } else {
        message.warning('该项目没有可用的分支');
      }
    } else {
      message.error(response.data.message || '加载分支列表失败');
    }
  } catch (error) {
    message.destroy();
    
    console.error('Load branches error:', error);
    
    if (error.code === 'ECONNABORTED' || error.message.includes('timeout')) {
      message.error('加载分支列表超时，请检查GitLab连接或稍后重试');
    } else if (error.response) {
      // 服务器返回错误响应
      const errorMsg = error.response.data?.message || '加载分支列表失败';
      if (error.response.status === 401) {
        message.error('GitLab认证失败，请检查Token配置');
      } else if (error.response.status === 404) {
        message.error('项目不存在或无权限访问');
      } else {
        message.error(errorMsg);
      }
    } else {
      message.error('网络连接失败，请检查网络连接');
    }
  } finally {
    branchLoading.value = false;
  }
};

// 处理分支变更
const handleBranchChange = async (branch) => {
  try {
    commitLoading.value = true;

    message.loading('正在加载提交记录...', 0);

    const token = localStorage.getItem('token');
    const response = await axios.get('/api/gitlab/commits/', {
      params: {
        task_id: selectedTask.value.task_id,
        branch: branch
      },
      headers: { 'Authorization': token },
      timeout: 30000 // 30秒超时
    });

    // 关闭加载提示
    message.destroy();

    if (response.data.code === 200) {
      commitList.value = response.data.data;
      if (commitList.value.length > 0) {
        buildForm.commit_id = commitList.value[0].id;
      } else {
        message.warning('该分支没有提交记录');
      }
    } else {
      message.error(response.data.message || '加载提交记录失败');
    }
  } catch (error) {
    message.destroy();
    
    console.error('Load commits error:', error);
    
    if (error.code === 'ECONNABORTED' || error.message.includes('timeout')) {
      message.error('加载提交记录超时，请检查GitLab连接或稍后重试');
    } else if (error.response) {
      const errorMsg = error.response.data?.message || '加载提交记录失败';
      if (error.response.status === 401) {
        message.error('GitLab认证失败，请检查Token配置');
      } else if (error.response.status === 404) {
        message.error('分支不存在或无权限访问');
      } else {
        message.error(errorMsg);
      }
    } else {
      message.error('网络连接失败，请检查网络连接');
    }
  } finally {
    commitLoading.value = false;
  }
};

// 处理构建方式变更
const handleBuildTypeChange = async () => {
  if (buildForm.buildType === 'rebuild') {
    buildForm.version = '';
    if (isStagingOrProdEnv.value) {
      await loadBranches();
    }
  } else {
    buildForm.branch = '';
    buildForm.commit_id = '';
    branchList.value = [];
    commitList.value = [];
  }
};

// 连接SSE
const connectSSE = (taskId, buildNumber, preserveLog = false) => {
  const protocol = window.location.protocol;
  const host = window.location.hostname;
  const port = window.location.port || (protocol === 'https:' ? '443' : '80');
  const baseUrl = `${protocol}//${host}:8900`;
  const sseUrl = `${baseUrl}/api/build/logs/stream/${taskId}/${buildNumber}/`;

  if (eventSource.value) {
    eventSource.value.close();
  }

  const token = localStorage.getItem('token');
  
  // 创建SSE连接
  eventSource.value = new EventSource(sseUrl + `?token=${encodeURIComponent(token)}`);

  eventSource.value.onopen = () => {
    if (!preserveLog) {
      buildLog.value = '';
    }
  };

  eventSource.value.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);

      if (data.type === 'connection_established') {
        if (!preserveLog) {
          buildLog.value = '连接成功，开始接收构建日志...\n';
        } else {
          buildLog.value += '\n重新连接成功，继续接收构建日志...\n';
        }
        
        // 滚动到底部
        nextTick(() => {
          if (logViewerRef.value?.forceScrollToBottom) {
            logViewerRef.value.forceScrollToBottom();
          }
        });
      } else if (data.type === 'build_log') {
        // 直接追加日志内容，不添加额外的换行
        buildLog.value += data.message;
        
        // 自动滚动（使用防抖的滚动）
        if (autoScroll.value) {
          nextTick(() => {
            if (logViewerRef.value?.scrollToBottom) {
              logViewerRef.value.scrollToBottom();
            }
          });
        }
      } else if (data.type === 'build_complete') {
        // 构建完成，显示提示信息
        if (data.message.includes('请使用历史日志API')) {
          // 这是已完成的构建，需要获取历史日志
          buildLog.value = '构建已完成，正在加载历史日志...\n';
          loadHistoryLog(selectedHistoryId.value);
        } else {
          // 构建完成后滚动到底部
          nextTick(() => {
            if (logViewerRef.value?.forceScrollToBottom) {
              logViewerRef.value.forceScrollToBottom();
            }
          });
        }
        
        // 构建完成后关闭连接
        closeSSE();
        // 刷新任务列表
        loadTasks();
      } else if (data.type === 'error') {
        buildLog.value += `错误: ${data.message}\n`;
        message.error(data.message);
        
        nextTick(() => {
          if (logViewerRef.value?.forceScrollToBottom) {
            logViewerRef.value.forceScrollToBottom();
          }
        });
      }
    } catch (error) {
      buildLog.value += event.data + '\n';
    }
  };

  // 处理心跳事件
  eventSource.value.addEventListener('heartbeat', (event) => {
    // 心跳事件，保持连接活跃，不需要特殊处理
  });

  eventSource.value.onclose = (event) => {
    if (event.code !== 1000) {
      buildLog.value += '\n连接已关闭\n';
    }
  };

  eventSource.value.onerror = (error) => {
    // SSE自动重连机制
    if (eventSource.value.readyState === EventSource.CLOSED) {
      buildLog.value += '\n连接失败\n';
      message.error('日志连接失败');
    } else {
      // 连接中断，尝试重连
      setTimeout(() => {
        if (logModalVisible.value && selectedTask.value) {
          buildLog.value += '\n尝试重新连接...\n';
          connectSSE(taskId, buildNumber, true); // 重连时保留日志
        }
      }, 3000); // 3秒后重连
    }
  };
};

// 加载历史日志的函数
const loadHistoryLog = async (historyId) => {
  try {
    const token = localStorage.getItem('token');
    const logResponse = await axios.get(`/api/build/history/log/${historyId}/`, {
      headers: { 'Authorization': token }
    });

    if (logResponse.data.code === 200) {
      buildLog.value = logResponse.data.data.log || '暂无日志';
      
      // 滚动到底部
      nextTick(() => {
        if (logViewerRef.value?.forceScrollToBottom) {
          logViewerRef.value.forceScrollToBottom();
        }
      });
    } else {
      buildLog.value = '加载历史日志失败';
    }
  } catch (error) {
    console.error('Load history log error:', error);
    buildLog.value = '加载历史日志失败';
  }
};

// 关闭SSE
const closeSSE = () => {
  if (eventSource.value) {
    eventSource.value.close();
    eventSource.value = null;
  }
};

// 验证版本号格式
const validateVersion = (version) => {
  // 版本号格式：YYYYMMDDHHmmSS_hash
  if (!version || version.length < 16) {
    return false;
  }

  // 检查格式: 14位数字(年月日时分秒)加下划线后跟8位提交ID
  const regex = /^\d{14}[_][a-zA-Z0-9]{8}$/;
  return regex.test(version);
};

// 确认构建
const confirmBuild = async () => {
  // 开发和测试环境需要选择分支
  if (isDevOrTestEnv.value && !buildForm.branch) {
    message.warning('请选择分支');
    return;
  }

  // 预发布和生产环境的验证逻辑
  if (isStagingOrProdEnv.value) {
    if (buildForm.buildType === 'existing_version') {
      // 使用已验证版本，需要输入版本号
      if (!buildForm.version) {
        message.warning('请输入版本号');
        return;
      }

      if (!validateVersion(buildForm.version)) {
        message.warning('版本号格式不正确，请输入类似 "20250320112507_029e149e" 的格式（年月日时分秒_提交ID前8位）');
        return;
      }
    } else if (buildForm.buildType === 'rebuild') {
      if (!buildForm.branch) {
        message.warning('请选择分支');
        return;
      }
    }
  }

  if (!buildForm.requirement) {
    message.warning('请输入构建需求描述');
    return;
  }

  try {
    buildConfirmLoading.value = true;

    // 清空并显示日志
    buildLog.value = '';
    logModalVisible.value = true;

    const token = localStorage.getItem('token');

    // 构建请求参数
    const requestData = {
      task_id: selectedTask.value.task_id,
      requirement: buildForm.requirement,
      parameter_values: buildForm.parameterValues
    };

    if (isDevOrTestEnv.value) {
      requestData.branch = buildForm.branch;
      requestData.commit_id = buildForm.commit_id;
    } else if (isStagingOrProdEnv.value) {
      if (buildForm.buildType === 'existing_version') {
        requestData.version = buildForm.version;
      } else if (buildForm.buildType === 'rebuild') {
        requestData.branch = buildForm.branch;
        requestData.commit_id = buildForm.commit_id;
      }
    }

    const response = await axios.post('/api/build/tasks/build', requestData, {
      headers: { 'Authorization': token }
    });

    if (response.data.code === 200) {
      message.success('开始构建');
      buildModalVisible.value = false;

      selectedTask.value.building_status = 'building';
      selectedTask.value.last_build = {
        id: response.data.data.history_id,
        number: response.data.data.build_number,
        status: 'running'
      };

      selectedHistoryId.value = response.data.data.history_id;

      // 使用返回的build_number连接SSE
      connectSSE(selectedTask.value.task_id, response.data.data.build_number);

      // 刷新任务列表
      loadTasks();
    }
  } catch (error) {
    console.error('Build task error:', error);
    message.error('构建失败');
    logModalVisible.value = false;
  } finally {
    buildConfirmLoading.value = false;
  }
};

// 处理日志模态框关闭
const handleLogModalClose = () => {
  stopLogUpdate();
  closeSSE();
  buildLog.value = '';
  logModalVisible.value = false;
  selectedHistoryId.value = '';
  selectedTask.value = null;
  // 刷新任务列表以显示最新状态
  loadTasks();
};

// 处理编辑任务
const handleEdit = (record) => {
  stopLogUpdate(); // 确保在跳转前清理定时器
  router.push({
    name: 'build-task-edit',
    query: { task_id: record.task_id }
  });
};

// 处理复制任务
const handleCopy = (record) => {
  // 检查权限
  const module = 'build_task';
  const action = 'create';
  if (!hasFunctionPermission(module, action)) {
    message.error('你没有创建构建任务的权限');
    return;
  }

  stopLogUpdate(); // 确保在跳转前清理定时器
  router.push({
    name: 'build-task-copy',
    query: { source_task_id: record.task_id }
  });
};

// 下载日志
const handleDownloadLog = async () => {
  if (!selectedHistoryId.value) {
    message.error('未找到构建历史记录');
    return;
  }

  try {
    const token = localStorage.getItem('token');
    const response = await axios.get(`/api/build/history/log/${selectedHistoryId.value}/`, {
      params: { download: true },
      headers: { 'Authorization': token },
      responseType: 'blob'
    });

    // 创建下载链接
    const url = window.URL.createObjectURL(new Blob([response.data]));
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', `build_log_${selectedTask.value?.name || 'unknown'}_${Date.now()}.txt`);
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(url);
  } catch (error) {
    console.error('Download log error:', error);
    message.error('下载日志失败');
  }
};

// 生命周期钩子
onMounted(() => {
  loadProjects();
  loadEnvironments();
  loadTasks();
});

onUnmounted(() => {
  stopLogUpdate();
  closeSSE();
});

const isDevOrTestEnv = computed(() => {
  return selectedTask.value && ['development', 'testing'].includes(selectedTask.value.environment?.type);
});

const isStagingOrProdEnv = computed(() => {
  return selectedTask.value && ['staging', 'production'].includes(selectedTask.value.environment?.type);
});

// 构建对话框标题
const buildModalTitle = computed(() => {
  return '构建配置';
});

// 处理构建历史页面跳转
const goToBuildHistory = () => {
  router.push('/build/history');
};

// 处理停止构建日志
const handleStopBuildInLog = async () => {
  try {
    if (!selectedTask.value || selectedTask.value.building_status !== 'building') {
      message.warning('没有正在进行的构建');
      return;
    }

    stopBuildLoading.value = true;
    const token = localStorage.getItem('token');
    const response = await axios.put('/api/build/tasks/build', {
      history_id: selectedTask.value.last_build.id
    }, {
      headers: { 'Authorization': token }
    });

    if (response.data.code === 200) {
      message.success('已停止构建');
      // 刷新任务列表
      loadTasks();
      // 更新当前任务状态
      selectedTask.value.building_status = 'idle';
    } else {
      message.error(response.data.message || '停止构建失败');
    }
  } catch (error) {
    console.error('Stop build in log error:', error);
    message.error('停止构建失败');
  } finally {
    stopBuildLoading.value = false;
  }
};

// 处理查看构建详情
const handleViewBuildDetail = (record) => {
  // 跳转到构建历史页面，并传递任务ID参数来筛选该任务的构建历史
  router.push({
    path: '/build/history',
    query: {
      task_id: record.task_id,
      task_name: record.name
    }
  });
};


</script>

<style scoped>

.page-header {
  margin-bottom: 24px;
}

.page-header h2 {
  margin: 0;
  color: rgba(0, 0, 0, 0.85);
  font-weight: 500;
}

.search-area {
  margin-bottom: 16px;
  right: 0;
}

:deep(.ant-card) {
  border-radius: 4px;
}

:deep(.ant-table-thead > tr > th) {
  background: #fafafa;
}

.build-info {
  font-size: 12px;
  color: rgba(0, 0, 0, 0.45);
  margin-top: 4px;
}

.log-content {
  display: flex;
  flex-direction: column;
  height: 650px;
  max-height: calc(100vh - 200px);
  overflow: hidden;
}

.log-viewer-container {
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

.log-body {
  flex: 1;
  overflow-y: auto;
  background: #1e1e1e;
  padding: 16px;
  font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', 'Consolas', monospace;
}

.log-body pre {
  margin: 0;
  color: #fff;
  white-space: pre-wrap;
  word-wrap: break-word;
}

.log-footer {
  padding: 12px;
}

.log-controls {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.left-controls {
  flex: 1;
}

.right-controls {
  flex: none;
}

.branch-commit-info {
  margin-left: 8px;
  color: rgba(0, 0, 0, 0.45);
  font-size: 12px;
}

.commit-list-wrapper {
  border: 1px solid #f0f0f0;
  border-radius: 4px;
  background: #fff;
}

.commit-list {
  max-height: 300px;
  overflow-y: auto;
}

.commit-item {
  width: 100%;
  padding: 8px 12px;
}

.commit-title {
  font-size: 14px;
  margin-bottom: 8px;
  font-weight: 500;
}

.commit-id {
  font-family: monospace;
  background: #f5f5f5;
  padding: 2px 4px;
  border-radius: 4px;
  margin-right: 8px;
  font-size: 12px;
  color: #666;
}

.commit-meta {
  font-size: 12px;
  color: rgba(0, 0, 0, 0.45);
  display: flex;
  gap: 16px;
  margin-bottom: 4px;
}

.commit-author,
.commit-time {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.commit-message {
  font-size: 12px;
  color: #666;
  margin-top: 4px;
  white-space: pre-line;
  word-break: break-all;
}

.commit-radio-group,
.commit-radio,
.build-preview {
  display: none;
}

/* 添加任务名称链接样式 */
:deep(.ant-table-cell) a {
  color: rgba(0, 0, 0, 0.85);
}

:deep(.ant-table-cell) a:hover {
    color: rgba(0, 0, 0, 0.65);
}

.version-tip {
  margin-top: 8px;
  font-size: 12px;
  color: rgba(0, 0, 0, 0.45);
}

.version-tip a {
  color: #1890ff;
  text-decoration: underline;
}

.last-build-info {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-height: 60px;
  /* padding: 8px 0; */
}

.build-number-status {
  display: flex;
  align-items: center;
  gap: 6px;
  /* margin-bottom: 4px; */
}

.build-number {
  font-weight: 600;
  color: #1890ff;
  font-size: 13px;
}

.build-number-link {
  text-decoration: none;
  cursor: pointer;
  transition: all 0.2s;
}

.build-number-link:hover {
  text-decoration: underline;
}

.build-number-link:hover .build-number {
  color: #40a9ff;
}

.build-status-tag {
  margin: 0;
  font-size: 11px;
  line-height: 1.2;
  border-radius: 4px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  text-align: center;
}

.build-details {
  display: flex;
  flex-direction: column;
  gap: 2px;
  font-size: 12px;
  color: #666;
}

.build-time,
.build-duration {
  display: flex;
  align-items: center;
  gap: 4px;
  line-height: 1.4;
}

.build-time .icon,
.build-duration .icon {
  font-size: 12px;
  color: #999;
}

.no-build {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 60px;
  color: #999;
  font-size: 12px;
}

.no-build-text {
  color: #999;
  font-size: 12px;
}

.task-status {
  display: flex;
  align-items: center;
  gap: 4px;
}

.building-tag {
  background-color: #1677ff;
  color: #fff;
  border-radius: 4px;
  padding: 2px 8px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
}

.task-status-tag {
  margin: 0;
  font-size: 12px;
  line-height: 1.2;
  border-radius: 4px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  text-align: center;
}

.spinning {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

.build-statistics {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.statistics-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.stat-item {
  display: flex;
  align-items: center;
  gap: 4px;
}

.stat-icon {
  font-size: 12px;
  color: #999;
}

.build-parameters {
  margin: 16px 0;
}

.parameter-group {
  margin-bottom: 16px;
}

.parameter-help {
  font-size: 12px;
  color: rgba(0, 0, 0, 0.45);
  margin-top: 4px;
}

.build-type-description {
  margin-top: 8px;
  font-size: 12px;
  color: rgba(0, 0, 0, 0.45);
}

.description-text {
  display: flex;
  align-items: center;
  gap: 4px;
}
</style>