import React, { useState, useEffect } from "react";
import { Modal, Form, Input, Select, Switch, message, Row, Col } from "antd";
import { User } from "../../../api/modules/users";

const { Option } = Select;

interface UserFormProps {
  visible: boolean;
  editingUser: User | null;
  onSubmit: (values: any) => Promise<void>;
  onCancel: () => void;
}

interface FormValues {
  username: string;
  email?: string;
  password?: string;
  confirmPassword?: string;
  role: string;
  is_active: boolean;
}

const UserForm: React.FC<UserFormProps> = ({
  visible,
  editingUser,
  onSubmit,
  onCancel,
}) => {
  const [form] = Form.useForm<FormValues>();
  const [loading, setLoading] = useState(false);
  const [passwordVisible, setPasswordVisible] = useState(false);

  // Initialize form with editing user data
  useEffect(() => {
    if (visible && editingUser) {
      form.setFieldsValue({
        username: editingUser.username,
        email: editingUser.email || "",
        password: "",
        confirmPassword: "",
        role: editingUser.role,
        is_active: editingUser.is_active,
      });
      setPasswordVisible(false);
    } else if (visible) {
      form.setFieldsValue({
        username: "",
        email: "",
        password: "",
        confirmPassword: "",
        role: "user",
        is_active: true,
      });
      setPasswordVisible(true);
    }
  }, [visible, editingUser, form]);

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      
      // Password validation for new users or password change
      if (!editingUser) {
        if (!values.password || !values.confirmPassword) {
          message.error("Password is required for new users");
          return;
        }
        if (values.password !== values.confirmPassword) {
          message.error("Passwords do not match");
          return;
        }
      } else if (values.password && values.password !== values.confirmPassword) {
        message.error("Passwords do not match");
        return;
      }

      // Prepare submission data
      const submitData: any = {
        username: values.username.trim(),
        email: values.email?.trim() || undefined,
        role: values.role,
        is_active: values.is_active,
      };

      // Only include password if provided
      if (values.password) {
        submitData.password = values.password;
      }

      setLoading(true);
      await onSubmit(submitData);
      form.resetFields();
    } catch (error) {
      console.error("Form validation failed:", error);
      // Validation errors are handled by Ant Design
    } finally {
      setLoading(false);
    }
  };

  const handleCancel = () => {
    form.resetFields();
    onCancel();
  };

  const validateUsername = (_: any, value: string) => {
    if (!value || value.trim().length < 3) {
      return Promise.reject(new Error("Username must be at least 3 characters"));
    }
    if (!/^[a-zA-Z0-9_.-]+$/.test(value)) {
      return Promise.reject(
        new Error("Username can only contain letters, numbers, dots, hyphens, and underscores")
      );
    }
    return Promise.resolve();
  };

  const validateEmail = (_: any, value: string) => {
    if (value && value.trim()) {
      const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
      if (!emailRegex.test(value)) {
        return Promise.reject(new Error("Please enter a valid email address"));
      }
    }
    return Promise.resolve();
  };

  const validatePassword = (_: any, value: string) => {
    if (!editingUser && !value) {
      return Promise.reject(new Error("Password is required for new users"));
    }
    if (value && value.length < 6) {
      return Promise.reject(new Error("Password must be at least 6 characters"));
    }
    return Promise.resolve();
  };

  const validateConfirmPassword = ({ getFieldValue }: any, value: string) => {
    if (!value && getFieldValue("password")) {
      return Promise.reject(new Error("Please confirm your password"));
    }
    if (value && getFieldValue("password") !== value) {
      return Promise.reject(new Error("Passwords do not match"));
    }
    return Promise.resolve();
  };

  return (
    <Modal
      title={editingUser ? "Edit User" : "Create User"}
      open={visible}
      onOk={handleSubmit}
      onCancel={handleCancel}
      confirmLoading={loading}
      width={600}
      okText={editingUser ? "Update" : "Create"}
      cancelText="Cancel"
      maskClosable={false}
      destroyOnClose
    >
      <Form
        form={form}
        layout="vertical"
        name="userForm"
        initialValues={{
          role: "user",
          is_active: true,
        }}
      >
        <Row gutter={16}>
          <Col span={12}>
            <Form.Item
              name="username"
              label="Username"
              rules={[
                { required: true, message: "Please enter username" },
                { validator: validateUsername },
              ]}
            >
              <Input placeholder="Enter username" />
            </Form.Item>
          </Col>
          <Col span={12}>
            <Form.Item
              name="email"
              label="Email"
              rules={[{ validator: validateEmail }]}
            >
              <Input placeholder="Enter email (optional)" />
            </Form.Item>
          </Col>
        </Row>

        {(!editingUser || passwordVisible) && (
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item
                name="password"
                label={editingUser ? "New Password" : "Password"}
                rules={[{ validator: validatePassword }]}
              >
                <Input.Password 
                  placeholder={editingUser ? "Leave blank to keep current" : "Enter password"} 
                />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                name="confirmPassword"
                label="Confirm Password"
                dependencies={["password"]}
                rules={[{ validator: validateConfirmPassword }]}
              >
                <Input.Password 
                  placeholder="Confirm password" 
                />
              </Form.Item>
            </Col>
          </Row>
        )}

        {editingUser && !passwordVisible && (
          <Form.Item>
            <a onClick={() => setPasswordVisible(true)}>
              Change password
            </a>
          </Form.Item>
        )}

        <Row gutter={16}>
          <Col span={12}>
            <Form.Item
              name="role"
              label="Role"
              rules={[{ required: true, message: "Please select a role" }]}
            >
              <Select placeholder="Select role">
                <Option value="user">User</Option>
                <Option value="admin">Administrator</Option>
              </Select>
            </Form.Item>
          </Col>
          <Col span={12}>
            <Form.Item
              name="is_active"
              label="Status"
              valuePropName="checked"
            >
              <Switch
                checkedChildren="Active"
                unCheckedChildren="Inactive"
              />
            </Form.Item>
          </Col>
        </Row>

        {editingUser && (
          <>
            <Form.Item label="User ID" style={{ marginBottom: 0 }}>
              <Input value={editingUser.id} disabled />
            </Form.Item>
            <Form.Item label="Created" style={{ marginBottom: 0 }}>
              <Input value={new Date(editingUser.created_at).toLocaleString()} disabled />
            </Form.Item>
            <Form.Item label="Last Login" style={{ marginBottom: 0 }}>
              <Input 
                value={editingUser.last_login 
                  ? new Date(editingUser.last_login).toLocaleString() 
                  : "Never"
                } 
                disabled 
              />
            </Form.Item>
          </>
        )}
      </Form>
    </Modal>
  );
};

export default UserForm;