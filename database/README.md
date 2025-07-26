# 数据库版本检测工具

## 概述

该目录包含用于生成和使用数据库版本检测SQL脚本的工具。这些工具可以帮助您检查数据库当前的版本状态，确定哪些Alembic迁移已经应用。

## 文件说明

- `gen_check_sql.py` - 用于生成数据库版本检测SQL脚本的Python脚本
- `check_db_version_generated.sql` - 自动生成的数据库版本检测SQL脚本（由gen_check_sql.py生成）
- `check_db_version.sql` - 手动维护的数据库版本检测SQL脚本

## 使用方法

### 生成数据库版本检测SQL脚本

运行以下命令生成数据库版本检测SQL脚本：

```bash
python database/gen_check_sql.py
```

这将在同一目录下生成 `check_db_version_generated.sql` 文件。

### 在数据库中执行检测脚本

使用psql或其他PostgreSQL客户端连接到数据库并执行生成的SQL脚本：

```bash
psql -h hostname -d database_name -U username -f database/check_db_version_generated.sql
```

或者在数据库客户端中复制粘贴脚本内容执行。

## 工作原理

生成的SQL脚本通过以下方式检测数据库版本：

1. 分析 `database/versions/` 目录下的所有Alembic迁移脚本
2. 识别每个版本的表结构变更（如添加列、创建索引等）
3. 识别每个版本的数据变更（如初始化配置等）
4. 为每个版本生成相应的检测SQL语句
5. 输出每个版本的变更是否已应用到当前数据库

## 输出说明

脚本执行后会输出一个表格，包含以下列：

- `version` - 版本号（如2.0.0, 2.0.1等）
- `change_applied` - 变更是否已应用（YES/NO/UNKNOWN）

## 注意事项

1. 生成的脚本主要针对表结构变更进行检测，对于纯数据变更可能无法准确判断
2. 某些复杂的变更可能被标记为UNKNOWN
3. 生成的脚本不会替代Alembic的版本管理机制，仅用于辅助诊断
4. 生成的SQL文件不会被打包到Docker镜像中