# Worklog CRM

为按项目交付的小团队管理工时。经理建项目并分配成员，员工按天登记工作分钟数，经理查看项目工时汇总，客户查看自己的项目状态。

- Django REST Framework 提供 API，JWT 用于登录和接口认证。
- PostgreSQL 保存公司、成员、项目和工时记录。每个员工每个项目每天可以登记一次，数据库约束防止重复入账。
- Redis 保存登录限流的共享状态，多个应用进程使用同一套限流记录。
- 经理只管理本公司的项目。员工只能登记分配给自己的在办项目，客户只能读取自己的项目状态。

## 本地启动

启动 Docker Desktop，在项目目录用 PowerShell 执行以下命令。

```powershell
Copy-Item .env.example .env
docker compose up --build --wait
docker compose exec app python manage.py seed_demo --password "Worklog-Local-7781"
```

演示账号为 `demo_manager`、`demo_employee`、`demo_client`，使用上一步设置的密码。应用启动时自动运行数据库迁移。

- [Swagger](http://localhost:8000/api/docs/)
- [健康检查](http://localhost:8000/health/)
- [管理后台](http://localhost:8000/admin/)

如需创建自己的公司和账号，运行 `docker compose exec app python manage.py createsuperuser`，然后在管理后台依次创建公司、用户和成员记录。

## 走一遍工时登记

1. 用员工账号调用 `POST /api/token/`，复制返回的 `access`，在 Swagger 的 **Authorize** 中填入。
2. 调用 `GET /api/projects/` 查看分配给自己的项目，并记下项目 ID。
3. 调用 `POST /api/worklogs/`，填写项目 ID、当天日期和工作分钟数。
4. 改用经理的令牌，调用 `GET /api/projects/{id}/summary/` 查看总分钟数和记录数。
5. 改用客户的令牌，可以查看自己项目的状态，工时接口会返回 403。

## 验证

安装 `requirements.txt` 后可以用 SQLite 和进程内缓存在本机快速运行测试。

```powershell
python manage.py test --settings=config.test_settings
```

GitHub Actions 使用真实的 PostgreSQL 和 Redis 执行相同测试，并从 Docker 镜像启动应用，验证健康检查和 Swagger 页面。
