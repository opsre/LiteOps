<template>
  <div class="credentials-list">
    <div class="page-header">
      <a-row justify="space-between" align="middle">
        <a-col>
          <h2>凭证管理</h2>
        </a-col>
        <a-col>
          <a-button type="primary" @click="showCreateModal">
            <template #icon><PlusOutlined /></template>
            添加凭证
          </a-button>
        </a-col>
      </a-row>
    </div>

    <a-card>
      <a-tabs v-model:activeKey="activeTab">
        <a-tab-pane key="gitlab_token" tab="GitLab Token凭证">
          <a-table
            :columns="columns"
            :data-source="credentials"
            :loading="loading"
            :pagination="false"
            :locale="{ emptyText: '暂无数据' }"
          >
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'action'">
                <a-space>
                  <a-button type="link" @click="handleEdit(record)">编辑</a-button>
                  <a-popconfirm
                    title="确定要删除这个凭证吗？"
                    @confirm="handleDelete(record)"
                  >
                    <a-button type="link" danger>删除</a-button>
                  </a-popconfirm>
                </a-space>
              </template>
            </template>
          </a-table>
        </a-tab-pane>

        <!-- GitHub Token凭证 Tab -->
        <a-tab-pane key="github_token" tab="GitHub Token凭证">
          <a-table
            :columns="columns"
            :data-source="credentials"
            :loading="loading"
            :pagination="false"
            :locale="{ emptyText: '暂无数据' }"
          >
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'action'">
                <a-space>
                  <a-button type="link" @click="handleEdit(record)">编辑</a-button>
                  <a-popconfirm
                    title="确定要删除这个凭证吗？"
                    @confirm="handleDelete(record)"
                  >
                    <a-button type="link" danger>删除</a-button>
                  </a-popconfirm>
                </a-space>
              </template>
            </template>
          </a-table>
        </a-tab-pane>

        <!-- SSH密钥凭证 Tab -->
        <a-tab-pane key="ssh_key" tab="SSH密钥凭证">
          <a-table
            :columns="columns"
            :data-source="credentials"
            :loading="loading"
            :pagination="false"
            :locale="{ emptyText: '暂无数据' }"
          >
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'deploy_status'">
                <a-tag :color="record.deployed ? 'rgba(135,208,104,0.8)' : 'rgba(128, 128, 128, 0.8)'">
                  {{ record.deploy_status }}
                </a-tag>
              </template>
              <template v-if="column.key === 'action'">
                <a-space>
                  <a-button type="link" @click="handleEdit(record)">编辑</a-button>
                  <a-button 
                    type="link" 
                    :loading="deployingCredentials[record.credential_id]"
                    @click="handleDeploy(record)"
                    v-if="!record.deployed"
                  >
                    部署
                  </a-button>
                  <a-button 
                    type="link" 
                    :loading="deployingCredentials[record.credential_id]"
                    @click="handleUndeploy(record)"
                    v-else
                  >
                    取消部署
                  </a-button>
                  <a-popconfirm
                    title="确定要删除这个凭证吗？"
                    @confirm="handleDelete(record)"
                  >
                    <a-button type="link" danger>删除</a-button>
                  </a-popconfirm>
                </a-space>
              </template>
            </template>
          </a-table>
        </a-tab-pane>

        <!-- Kubeconfig凭证 Tab -->
        <a-tab-pane key="kubeconfig" tab="Kubeconfig凭证">
          <a-table
            :columns="columns"
            :data-source="credentials"
            :loading="loading"
            :pagination="false"
            :locale="{ emptyText: '暂无数据' }"
          >
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'cluster_name'">
                <span>{{ record.cluster_name }}</span>
              </template>
              <template v-if="column.key === 'context_name'">
                <code>liteops-{{ record.context_name }}</code>
              </template>
              <template v-if="column.key === 'deploy_status'">
                <a-tag :color="record.deployed ? 'rgba(135,208,104,0.8)' : 'rgba(128, 128, 128, 0.8)'">
                  {{ record.deploy_status }}
                </a-tag>
              </template>
              <template v-if="column.key === 'action'">
                <a-space>
                  <a-button type="link" @click="handleEdit(record)">编辑</a-button>
                  <a-button 
                    type="link" 
                    :loading="deployingCredentials[record.credential_id]"
                    @click="handleKubeconfigDeploy(record)"
                    v-if="!record.deployed"
                  >
                    部署
                  </a-button>
                  <a-button 
                    type="link" 
                    :loading="deployingCredentials[record.credential_id]"
                    @click="handleKubeconfigUndeploy(record)"
                    v-else
                  >
                    取消部署
                  </a-button>
                  <a-popconfirm
                    title="确定要删除这个凭证吗？删除后将重新部署剩余的配置。"
                    @confirm="handleDelete(record)"
                  >
                    <a-button type="link" danger>删除</a-button>
                  </a-popconfirm>
                </a-space>
              </template>
            </template>
          </a-table>
        </a-tab-pane>

      </a-tabs>
    </a-card>

    <!-- 凭证表单弹窗 -->
    <a-modal
      v-model:open="modalVisible"
      :title="editingCredential ? '编辑凭证' : '添加凭证'"
      @ok="handleModalOk"
      :confirmLoading="submitLoading"
      width="600px"
    >
      <a-form
        ref="formRef"
        :model="formState"
        :rules="rules"
        layout="vertical"
      >
        <a-form-item label="凭证名称" name="name">
          <a-input v-model:value="formState.name" placeholder="请输入凭证名称" />
        </a-form-item>

        <a-form-item label="凭证描述" name="description">
          <a-textarea
            v-model:value="formState.description"
            placeholder="请输入凭证描述"
            :rows="2"
          />
        </a-form-item>

        <!-- GitLab Token凭证表单 -->
        <template v-if="activeTab === 'gitlab_token'">
          <a-form-item label="GitLab Token" name="token">
            <a-input-password v-model:value="formState.token" placeholder="请输入GitLab Token" />
          </a-form-item>
        </template>

        <!-- SSH密钥凭证表单 -->
        <template v-if="activeTab === 'ssh_key'">
          <a-form-item label="SSH私钥内容" name="private_key">
            <div style="display: flex; flex-direction: column; gap: 8px;">
              <a-textarea
                v-model:value="formState.private_key"
                placeholder="请输入完整的SSH私钥内容"
                :rows="8"
              />
              <a-upload
                name="file"
                :multiple="false"
                :showUploadList="false"
                :beforeUpload="handleUploadPrivateKey"
              >
                <a-button>
                  <template #icon><UploadOutlined /></template>
                  上传私钥文件
                </a-button>
              </a-upload>
            </div>
          </a-form-item>
          <a-form-item label="私钥密码 (可选)" name="passphrase">
            <a-input-password v-model:value="formState.passphrase" placeholder="如果私钥有密码保护，请输入密码" />
          </a-form-item>
        </template>

        <!-- GitHub Token凭证表单 -->
        <template v-if="activeTab === 'github_token'">
          <a-form-item label="GitHub Token" name="token">
            <a-input-password v-model:value="formState.token" placeholder="请输入GitHub Token" />
          </a-form-item>
          <a-alert
            message="GitHub Token使用说明"
            type="info"
            show-icon
          >
            <template #description>
              <div>
                <p>• 需要在GitHub上生成个人访问令牌（Personal Access Token）</p>
                <p>• 令牌需要具有repo权限以访问私有仓库</p>
                <p>• 建议使用具有最小必要权限的令牌</p>
              </div>
            </template>
          </a-alert>
        </template>

        <!-- Kubeconfig凭证表单 -->
        <template v-if="activeTab === 'kubeconfig'">
          <a-form-item label="Kubeconfig配置内容" name="kubeconfig_content">
            <div style="display: flex; flex-direction: column; gap: 8px;">
              <a-textarea
                v-model:value="formState.kubeconfig_content"
                placeholder="请输入完整的Kubeconfig配置内容（YAML格式）"
                :rows="5"
              />
              <a-upload
                name="file"
                :multiple="false"
                :showUploadList="false"
                :beforeUpload="handleUploadKubeconfig"
              >
                <a-button>
                  <template #icon><UploadOutlined /></template>
                  上传Kubeconfig文件
                </a-button>
              </a-upload>
            </div>
          </a-form-item>
          <a-alert
            message="使用说明"
            type="info"
            show-icon
          >
            <template #description>
              <div>
                <p>• 上传或粘贴你的Kubeconfig文件内容</p>
                <p>• 系统将自动解析并提取集群和上下文信息</p>
                <p>• 部署后，上下文名称将添加 "liteops-" 前缀以避免冲突</p>
              </div>
            </template>
          </a-alert>
        </template>

      </a-form>
    </a-modal>

    <!-- SSH密钥部署弹窗 -->
    <a-modal
      v-model:open="deployModalVisible"
      title="部署SSH密钥"
      @ok="handleDeployConfirm"
      :confirmLoading="deployLoading"
      width="500px"
    >
      <a-alert
        message="部署说明"
        type="info"
        show-icon
      >
        <template #description>
          <div>
            <p>部署后，该SSH密钥将被配置到CI/CD容器中，你可以在构建脚本中直接使用：</p>
            <p><code>ssh user@your-server-ip</code></p>
            <p>来连接到远程服务器进行部署操作。</p>
          </div>
        </template>
      </a-alert>
    </a-modal>

    <!-- 部署结果弹窗 -->
    <a-modal
      v-model:open="deployResultModalVisible"
      title="部署结果"
      :footer="null"
      width="600px"
    >
      <a-result
        :status="deployResult.success ? 'success' : 'error'"
        :title="deployResult.success ? '部署成功' : '部署失败'"
        :sub-title="deployResult.message"
      >
        <template #extra v-if="deployResult.success && deployResult.data">
          <div style="text-align: left; background: #f5f5f5; padding: 16px; border-radius: 4px; margin: 16px 0;">
            <!-- SSH密钥使用说明 -->
            <template v-if="deployResult.data.key_file">
              <h4>使用说明：</h4>
              <p><strong>密钥文件：</strong> <code>{{ deployResult.data.key_file }}</code></p>
              <p><strong>使用示例：</strong> <code>{{ deployResult.data.usage_example }}</code></p>
              <p><strong>在构建脚本中使用：</strong></p>
              <pre style="background: white; padding: 8px; border-radius: 4px;">ssh root@192.168.1.100
ssh user@your-server-ip</pre>
            </template>
            <!-- Kubeconfig使用说明 -->
            <template v-if="deployResult.data.usage_info">
              <pre style="background: white; padding: 12px; border-radius: 4px; white-space: pre-wrap; font-family: 'Monaco', 'Consolas', monospace; font-size: 12px; line-height: 1.5;">{{ deployResult.data.usage_info }}</pre>
            </template>
          </div>
          <a-button type="primary" @click="deployResultModalVisible = false">知道了</a-button>
        </template>
        <template #extra v-else>
          <a-button @click="deployResultModalVisible = false">关闭</a-button>
        </template>
      </a-result>
    </a-modal>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, watch } from 'vue';
import { message } from 'ant-design-vue';
import { PlusOutlined, UploadOutlined } from '@ant-design/icons-vue';
import axios from 'axios';
import { checkPermission, hasFunctionPermission } from '../../utils/permission';

const activeTab = ref('gitlab_token');
const loading = ref(false);
const submitLoading = ref(false);
const credentials = ref([]);
const modalVisible = ref(false);
const editingCredential = ref(null);
const formRef = ref();

// 部署相关状态
const deployModalVisible = ref(false);
const deployResultModalVisible = ref(false);
const deployLoading = ref(false);
const currentDeployCredential = ref(null);
const deployingCredentials = ref({});
const deployResult = ref({
  success: false,
  message: '',
  data: null
});

// 表格列定义
const baseColumns = [
  {
    title: '凭证名称',
    dataIndex: 'name',
    key: 'name',
  },
  {
    title: '创建者',
    key: 'creator',
    customRender: ({ record }) => record.creator?.name || '未知',
  },
  {
    title: '描述',
    dataIndex: 'description',
    key: 'description',
    ellipsis: true,
  },
  {
    title: '创建时间',
    dataIndex: 'create_time',
    key: 'create_time',
  },
  {
    title: '操作',
    key: 'action',
    // width: 200,
  },
];

const sshKeyColumns = [
  ...baseColumns.slice(0, 1),
  {
    title: '部署状态',
    key: 'deploy_status',
  },
  ...baseColumns.slice(1, -1),
  {
    title: '操作',
    key: 'action',
  },
];

const kubeconfigColumns = [
  ...baseColumns.slice(0, 1),
  {
    title: '集群名称',
    key: 'cluster_name',
  },
  {
    title: '上下文名称',
    key: 'context_name',
    ellipsis: true,
  },
  {
    title: '部署状态',
    key: 'deploy_status',
  },
  ...baseColumns.slice(1, -1),
  {
    title: '操作',
    key: 'action',
  },
];

// 根据当前选中的标签页获取对应的列定义
const columns = computed(() => {
  switch (activeTab.value) {
    case 'gitlab_token':
      return baseColumns;
    case 'ssh_key':
      return sshKeyColumns;
    case 'kubeconfig':
      return kubeconfigColumns;
    default:
      return baseColumns;
  }
});

const formState = reactive({
  name: '',
  description: '',
  token: '',
  private_key: '',
  passphrase: '',
  kubeconfig_content: '',
  type: '',
});

const rules = computed(() => {
  const baseRules = {
    name: [{ required: true, message: '请输入凭证名称' }],
    description: [{ required: false, message: '请输入凭证描述' }],
  };

  // 根据不同的凭证类型返回不同的验证规则
  switch (activeTab.value) {
    case 'gitlab_token':
    case 'github_token':
      return {
        ...baseRules,
        token: [{ required: !editingCredential.value, message: `请输入${activeTab.value === 'gitlab_token' ? 'GitLab' : 'GitHub'} Token` }],
      };
    case 'ssh_key':
      return {
        ...baseRules,
        private_key: [{ required: !editingCredential.value, message: '请输入SSH私钥内容' }],
        passphrase: [{ required: false }]
      };
    case 'kubeconfig':
      return {
        ...baseRules,
        kubeconfig_content: [{ required: !editingCredential.value, message: '请输入Kubeconfig配置内容' }]
      };
    default:
      return baseRules;
  }
});

// 加载凭证列表
const loadCredentials = async () => {
  // 检查查看权限
  if (!checkPermission('credential', 'view')) {
    return;
  }

  loading.value = true;
  try {
    const token = localStorage.getItem('token');
    const response = await axios.get('/api/credentials/', {
      headers: {
        'Authorization': token
      },
      params: {
        type: activeTab.value
      }
    });

    if (response.data.code === 200) {
      credentials.value = response.data.data.map(item => ({
        ...item,
        key: item.credential_id
      }));
    } else {
      message.error(response.data.message || '加载凭证列表失败');
    }
  } catch (error) {
    message.error('加载凭证列表失败');
    console.error('Load credentials error:', error);
  } finally {
    loading.value = false;
  }
};

// 重置表单状态
const resetFormState = () => {
  Object.keys(formState).forEach(key => {
    formState[key] = '';
  });
  formState.type = activeTab.value;
};

// 显示创建模态框
const showCreateModal = () => {
  if (!checkPermission('credential', 'create')) {
    return;
  }
  editingCredential.value = null;
  resetFormState();
  modalVisible.value = true;
};

const handleEdit = (record) => {
  if (!checkPermission('credential', 'edit')) {
    return;
  }

  editingCredential.value = record;

  // 根据凭证类型设置表单值
  const commonFields = {
    name: record.name,
    description: record.description,
  };

  switch (activeTab.value) {
    case 'gitlab_token':
    case 'github_token':
      Object.assign(formState, {
        ...commonFields,
        // 不回显token
      });
      break;
    case 'ssh_key':
      Object.assign(formState, {
        ...commonFields,
        // 不回显私钥和密码
      });
      break;
    case 'kubeconfig':
      Object.assign(formState, {
        ...commonFields,
        // 不回显kubeconfig内容
      });
      break;
  }

  modalVisible.value = true;
};

// 处理删除
const handleDelete = async (record) => {
  if (!checkPermission('credential', 'delete')) {
    return;
  }

  try {
    const token = localStorage.getItem('token');
    const response = await axios.delete('/api/credentials/', {
      headers: {
        'Authorization': token
      },
      data: {
        credential_id: record.credential_id,
        type: activeTab.value
      }
    });

    if (response.data.code === 200) {
      message.success('删除成功');
      await loadCredentials();
    } else {
      message.error(response.data.message || '删除失败');
    }
  } catch (error) {
    message.error('删除失败');
    console.error('Delete credential error:', error);
  }
};

// 处理部署
const handleDeploy = (record) => {
  if (!checkPermission('credential', 'edit')) {
    return;
  }
  
  currentDeployCredential.value = record;
  deployModalVisible.value = true;
};

// 确认部署
const handleDeployConfirm = async () => {
  if (!currentDeployCredential.value) return;
  
  deployLoading.value = true;
  deployingCredentials.value[currentDeployCredential.value.credential_id] = true;
  
  try {
    const token = localStorage.getItem('token');
    const response = await axios.post('/api/credentials/', {
      action: 'deploy',
      credential_id: currentDeployCredential.value.credential_id
    }, {
      headers: {
        'Authorization': token
      }
    });

    if (response.data.code === 200) {
      deployResult.value = {
        success: true,
        message: response.data.message,
        data: response.data.data
      };
      deployModalVisible.value = false;
      deployResultModalVisible.value = true;
      message.success('部署成功');
      await loadCredentials();
    } else {
      deployResult.value = {
        success: false,
        message: response.data.message,
        data: null
      };
      deployResultModalVisible.value = true;
    }
  } catch (error) {
    deployResult.value = {
      success: false,
      message: error.response?.data?.message || '部署失败',
      data: null
    };
    deployResultModalVisible.value = true;
    console.error('Deploy SSH key error:', error);
  } finally {
    deployLoading.value = false;
    deployingCredentials.value[currentDeployCredential.value.credential_id] = false;
    deployModalVisible.value = false;
  }
};

// 处理取消部署
const handleUndeploy = async (record) => {
  if (!checkPermission('credential', 'edit')) {
    return;
  }
  
  deployingCredentials.value[record.credential_id] = true;
  
  try {
    const token = localStorage.getItem('token');
    const response = await axios.post('/api/credentials/', {
      action: 'undeploy',
      credential_id: record.credential_id
    }, {
      headers: {
        'Authorization': token
      }
    });

    if (response.data.code === 200) {
      message.success('取消部署成功');
      await loadCredentials();
    } else {
      message.error(response.data.message || '取消部署失败');
    }
  } catch (error) {
    message.error('取消部署失败');
    console.error('Undeploy SSH key error:', error);
  } finally {
    deployingCredentials.value[record.credential_id] = false;
  }
};

// 处理私钥文件上传
const handleUploadPrivateKey = (file) => {
  const reader = new FileReader();
  reader.onload = (e) => {
    formState.private_key = e.target.result;
    message.success('私钥文件已上传');
  };
  reader.onerror = () => {
    message.error('读取文件失败');
  };
  reader.readAsText(file);
  return false; 
};

// 处理Kubeconfig文件上传
const handleUploadKubeconfig = (file) => {
  const reader = new FileReader();
  reader.onload = (e) => {
    formState.kubeconfig_content = e.target.result;
    message.success('Kubeconfig文件已上传');
  };
  reader.onerror = () => {
    message.error('读取文件失败');
  };
  reader.readAsText(file);
  return false;
};

// 处理模态框确认
const handleModalOk = async () => {
  try {
    await formRef.value.validate();
    submitLoading.value = true;

    const token = localStorage.getItem('token');
    const data = {
      name: formState.name,
      description: formState.description,
      type: activeTab.value,
    };

    // 根据凭证类型添加不同的字段
    switch (activeTab.value) {
      case 'gitlab_token':
      case 'github_token':
        Object.assign(data, {
          token: formState.token,
        });
        break;
      case 'ssh_key':
        Object.assign(data, {
          private_key: formState.private_key,
          passphrase: formState.passphrase,
        });
        break;
      case 'kubeconfig':
        Object.assign(data, {
          kubeconfig_content: formState.kubeconfig_content,
        });
        break;
    }

    if (editingCredential.value) {
      data.credential_id = editingCredential.value.credential_id;
    }

    const response = await axios({
      method: editingCredential.value ? 'put' : 'post',
      url: '/api/credentials/',
      headers: {
        'Authorization': token
      },
      data
    });

    if (response.data.code === 200) {
      message.success(editingCredential.value ? '更新成功' : '创建成功');
      modalVisible.value = false;
      await loadCredentials();
    } else {
      throw new Error(response.data.message || (editingCredential.value ? '更新失败' : '创建失败'));
    }
  } catch (error) {
    message.error(error.response?.data?.message || error.message);
    console.error('Save credential error:', error);
  } finally {
    submitLoading.value = false;
  }
};

// 监听标签页切换
watch(activeTab, () => {
  loadCredentials();
});

// 处理Kubeconfig单独部署
const handleKubeconfigDeploy = async (record) => {
  if (!checkPermission('credential', 'edit')) {
    return;
  }
  
  deployingCredentials.value[record.credential_id] = true;
  
  try {
    const token = localStorage.getItem('token');
    const response = await axios.post('/api/credentials/', {
      action: 'deploy_kubeconfig',
      credential_id: record.credential_id
    }, {
      headers: {
        'Authorization': token
      }
    });

    if (response.data.code === 200) {
      // 生成前端的使用说明
      const usageInfo = generateKubeconfigUsageInfo(record);
      deployResult.value = {
        success: true,
        message: '部署成功',
        data: {
          usage_info: usageInfo
        }
      };
      deployResultModalVisible.value = true;
      message.success('部署成功');
      await loadCredentials();
    } else {
      deployResult.value = {
        success: false,
        message: response.data.message,
        data: null
      };
      deployResultModalVisible.value = true;
    }
  } catch (error) {
    deployResult.value = {
      success: false,
      message: error.response?.data?.message || '部署失败',
      data: null
    };
    deployResultModalVisible.value = true;
    console.error('Deploy kubeconfig error:', error);
  } finally {
    deployingCredentials.value[record.credential_id] = false;
  }
};

// 处理Kubeconfig单独取消部署
const handleKubeconfigUndeploy = async (record) => {
  if (!checkPermission('credential', 'edit')) {
    return;
  }
  
  deployingCredentials.value[record.credential_id] = true;
  
  try {
    const token = localStorage.getItem('token');
    const response = await axios.post('/api/credentials/', {
      action: 'undeploy_kubeconfig',
      credential_id: record.credential_id
    }, {
      headers: {
        'Authorization': token
      }
    });

    if (response.data.code === 200) {
      message.success('取消部署成功');
      await loadCredentials();
    } else {
      message.error(response.data.message || '取消部署失败');
    }
  } catch (error) {
    message.error('取消部署失败');
    console.error('Undeploy kubeconfig error:', error);
  } finally {
    deployingCredentials.value[record.credential_id] = false;
  }
};

// 生成Kubeconfig使用说明
const generateKubeconfigUsageInfo = (record) => {
  const contextName = `liteops-${record.context_name}`;
  return `Kubeconfig部署成功！

集群信息:
  集群名称: ${record.cluster_name}
  上下文名称: ${contextName}

使用方法:
1. 查看所有上下文:
   kubectl config get-contexts

2. 切换到此集群:
   kubectl config use-context ${contextName}

3. 验证当前集群连接:
   kubectl cluster-info

4. 查看集群节点:
   kubectl get nodes

注意: 该配置已合并到 ~/.kube/config 文件中`;
};

onMounted(() => {
  if (!hasFunctionPermission('credential', 'view')) {
    message.warning('你没有凭证查看权限，部分功能可能受限');
  }
  loadCredentials();
});
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

:deep(.ant-card) {
  border-radius: 4px;
}

:deep(.ant-tabs-nav) {
  margin-bottom: 16px;
}

:deep(.ant-table-thead > tr > th) {
  background: #fafafa;
}

:where(.css-dev-only-do-not-override-mdfpa0).ant-result {
    padding: 0px;
}
</style>