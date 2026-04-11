import React, { useState, useEffect } from "react";
import { Card, Table, Button, Input, Modal, message, Tag, Space } from "antd";
import {
  PlusOutlined,
  EditOutlined,
  DeleteOutlined,
  SearchOutlined,
  ReloadOutlined,
} from "@ant-design/icons";
import type { ColumnsType } from "antd/es/table";
import { getApiToken } from "../../../api/config";
import { authApi } from "../../../api/modules/auth";
import { usersApi, User } from "../../../api/modules/users";
import UserForm from "./UserForm";
import "./index.less";

interface UserListFilters {
  username?: string;
  email?: string;
  role?: string;
  is_active?: boolean;
}

const UsersPage: React.FC = () => {
  const token = getApiToken();
  const [currentUser, setCurrentUser] = useState<{ user_id?: number; role: string; username: string } | null>(null);

  useEffect(() => {
    if (!token) return;
    authApi.verify(token).then((info) => setCurrentUser(info)).catch(() => {});
  }, [token]);
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(false);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [searchText, setSearchText] = useState("");
  const [filters, setFilters] = useState<UserListFilters>({});
  const [formVisible, setFormVisible] = useState(false);
  const [editingUser, setEditingUser] = useState<User | null>(null);
  const [deleteModalVisible, setDeleteModalVisible] = useState(false);
  const [userToDelete, setUserToDelete] = useState<User | null>(null);

  // Load users
  const loadUsers = async () => {
    if (!token) return;
    
    setLoading(true);
    try {
      const response = await usersApi.list(token, {
        skip: (page - 1) * pageSize,
        limit: pageSize,
        active_only: filters.is_active,
      });

      // Apply client-side filtering for search
      let filteredUsers = response.users;
      if (searchText) {
        const searchTerm = searchText.toLowerCase();
        filteredUsers = filteredUsers.filter(
          (user) =>
            user.username.toLowerCase().includes(searchTerm) ||
            (user.email && user.email.toLowerCase().includes(searchTerm))
        );
      }

      setUsers(filteredUsers);
      setTotal(response.total);
    } catch (error) {
      console.error("Failed to load users:", error);
      message.error("Failed to load users");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadUsers();
  }, [token, page, pageSize, filters]);

  const handleSearch = () => {
    loadUsers();
  };

  const handleReset = () => {
    setSearchText("");
    setFilters({});
    setPage(1);
    loadUsers();
  };

  const handleCreate = () => {
    setEditingUser(null);
    setFormVisible(true);
  };

  const handleEdit = (user: User) => {
    setEditingUser(user);
    setFormVisible(true);
  };

  const handleDelete = (user: User) => {
    setUserToDelete(user);
    setDeleteModalVisible(true);
  };

  const confirmDelete = async () => {
    if (!token || !userToDelete) return;

    try {
      await usersApi.delete(token, userToDelete.id);
      message.success("User deleted successfully");
      setDeleteModalVisible(false);
      setUserToDelete(null);
      loadUsers();
    } catch (error) {
      console.error("Failed to delete user:", error);
      message.error("Failed to delete user");
    }
  };

  const handleFormSubmit = async (values: any) => {
    if (!token) return;

    try {
      if (editingUser) {
        await usersApi.update(
          token,
          editingUser.id,
          values
        );
        message.success("User updated successfully");
      } else {
        await usersApi.create(token, {
          ...values,
          role: values.role || "user",
        });
        message.success("User created successfully");
      }

      setFormVisible(false);
      setEditingUser(null);
      loadUsers();
    } catch (error: any) {
      console.error("Failed to save user:", error);
      message.error(error.message || "Failed to save user");
    }
  };

  const handleResetPassword = async (user: User) => {
    Modal.confirm({
      title: "Reset Password",
      content: (
        <div>
          <p>Are you sure you want to reset password for user "{user.username}"?</p>
          <p>A new temporary password will be generated and displayed.</p>
        </div>
      ),
      onOk: async () => {
        try {
          if (!token) return;
          
          // Generate a random password
          const newPassword = Math.random().toString(36).slice(-8) + "A1!";
          
          await usersApi.resetPassword(token, user.id, {
            new_password: newPassword,
          });
          
          Modal.success({
            title: "Password Reset Successful",
            content: (
              <div>
                <p>New password for user "{user.username}":</p>
                <p style={{ 
                  fontSize: "16px", 
                  fontWeight: "bold",
                  backgroundColor: "#f5f5f5",
                  padding: "8px",
                  borderRadius: "4px",
                  fontFamily: "monospace",
                }}>
                  {newPassword}
                </p>
                <p style={{ color: "#ff4d4f", marginTop: "8px" }}>
                  Please copy this password now. It will not be shown again.
                </p>
              </div>
            ),
            width: 500,
          });
        } catch (error: any) {
          console.error("Failed to reset password:", error);
          message.error(error.message || "Failed to reset password");
        }
      },
    });
  };

  const columns: ColumnsType<User> = [
    {
      title: "Username",
      dataIndex: "username",
      key: "username",
      sorter: (a, b) => a.username.localeCompare(b.username),
    },
    {
      title: "Email",
      dataIndex: "email",
      key: "email",
      render: (email) => email || "-",
    },
    {
      title: "Role",
      dataIndex: "role",
      key: "role",
      render: (role) => (
        <Tag color={role === "admin" ? "purple" : "cyan"}>
          {usersApi.formatRole(role)}
        </Tag>
      ),
      filters: [
        { text: "Admin", value: "admin" },
        { text: "User", value: "user" },
      ],
      onFilter: (value, record) => record.role === value,
    },
    {
      title: "Status",
      dataIndex: "is_active",
      key: "is_active",
      render: (isActive) => (
        <Tag color={isActive ? "green" : "red"}>
          {isActive ? "Active" : "Inactive"}
        </Tag>
      ),
      filters: [
        { text: "Active", value: true },
        { text: "Inactive", value: false },
      ],
      onFilter: (value, record) => record.is_active === value,
    },
    {
      title: "Created",
      dataIndex: "created_at",
      key: "created_at",
      render: (date) => usersApi.formatDate(date),
      sorter: (a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime(),
    },
    {
      title: "Last Login",
      dataIndex: "last_login",
      key: "last_login",
      render: (date) => usersApi.formatDate(date),
      sorter: (a, b) => {
        const dateA = a.last_login ? new Date(a.last_login).getTime() : 0;
        const dateB = b.last_login ? new Date(b.last_login).getTime() : 0;
        return dateA - dateB;
      },
    },
    {
      title: "Actions",
      key: "actions",
      render: (_, record) => {
        const isCurrentUser = currentUser?.user_id === record.id;
        
        return (
          <Space size="small">
            <Button
              type="link"
              icon={<EditOutlined />}
              onClick={() => handleEdit(record)}
              disabled={isCurrentUser}
            >
              Edit
            </Button>
            <Button
              type="link"
              danger
              icon={<DeleteOutlined />}
              onClick={() => handleDelete(record)}
              disabled={isCurrentUser || record.role === "admin"}
            >
              Delete
            </Button>
            <Button
              type="link"
              onClick={() => handleResetPassword(record)}
            >
              Reset Password
            </Button>
          </Space>
        );
      },
    },
  ];

  // Check if current user is admin
  if (currentUser?.role !== "admin") {
    return (
      <Card>
        <div style={{ textAlign: "center", padding: "40px" }}>
          <h2>Access Denied</h2>
          <p>You do not have permission to access user management.</p>
          <p>Only administrators can manage users.</p>
        </div>
      </Card>
    );
  }

  return (
    <div className="users-page">
      <Card
        title="User Management"
        extra={
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={handleCreate}
          >
            Add User
          </Button>
        }
      >
        <div className="users-search">
          <Input
            placeholder="Search by username or email"
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
            onPressEnter={handleSearch}
            style={{ width: 300, marginRight: 16 }}
            prefix={<SearchOutlined />}
          />
          <Button
            type="primary"
            onClick={handleSearch}
            style={{ marginRight: 8 }}
          >
            Search
          </Button>
          <Button onClick={handleReset} style={{ marginRight: 16 }}>
            Reset
          </Button>
          <Button
            icon={<ReloadOutlined />}
            onClick={loadUsers}
            loading={loading}
          >
            Refresh
          </Button>
        </div>

        <Table
          columns={columns}
          dataSource={users}
          rowKey="id"
          loading={loading}
          pagination={{
            current: page,
            pageSize: pageSize,
            total: total,
            showSizeChanger: true,
            showTotal: (total, range) =>
              `${range[0]}-${range[1]} of ${total} users`,
            onChange: (newPage, newPageSize) => {
              setPage(newPage);
              setPageSize(newPageSize);
            },
          }}
          locale={{
            emptyText: "No users found",
          }}
        />
      </Card>

      {/* User Form Modal */}
      <UserForm
        visible={formVisible}
        editingUser={editingUser}
        onSubmit={handleFormSubmit}
        onCancel={() => {
          setFormVisible(false);
          setEditingUser(null);
        }}
      />

      {/* Delete Confirmation Modal */}
      <Modal
        title="Delete User"
        open={deleteModalVisible}
        onOk={confirmDelete}
        onCancel={() => {
          setDeleteModalVisible(false);
          setUserToDelete(null);
        }}
        okText="Delete"
        okType="danger"
        cancelText="Cancel"
      >
        {userToDelete && (
          <div>
            <p>Are you sure you want to delete user "{userToDelete.username}"?</p>
            <p style={{ color: "#ff4d4f" }}>
              Note: This will deactivate the user. The user will not be able to login,
              but their data will be preserved.
            </p>
          </div>
        )}
      </Modal>
    </div>
  );
};

export default UsersPage;