#!/usr/bin/env python3
"""
用于生成数据库版本检测SQL文件的脚本
该脚本会分析Alembic版本文件并生成相应的SQL检测脚本
"""

import os
import re
from pathlib import Path


def get_version_info(version_file):
    """
    从版本文件中提取版本信息
    """
    with open(version_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 提取版本号和描述
    version_match = re.search(r"Revision ID: ([0-9a-f]+)", content)
    description_match = re.search(r'"""(.+?)\n', content)
    
    version_id = version_match.group(1) if version_match else "unknown"
    description = description_match.group(1) if description_match else "未知版本"
    
    # 提取版本号（如2.0.0）
    version_number = "unknown"
    version_number_match = re.search(r'(\d+\.\d+\.\d+)', description)
    if version_number_match:
        version_number = version_number_match.group(1)
    
    return {
        'version_id': version_id,
        'version_number': version_number,
        'description': description,
        'content': content
    }


def extract_changes(version_info):
    """
    从版本文件中提取变更信息
    """
    content = version_info['content']
    
    changes = {
        'table_changes': [],  # 表结构变更
        'data_changes': [],   # 数据变更
        'unknown_changes': [] # 无法确定的变更
    }
    
    # 查找添加列的操作
    add_column_matches = re.findall(r"op\.add_column\('(\w+)', sa\.Column\('(\w+)'", content)
    for table, column in add_column_matches:
        changes['table_changes'].append({
            'type': 'add_column',
            'table': table,
            'column': column
        })
    
    # 查找创建索引的操作
    create_index_matches = re.findall(r"op\.create_index\('(\w+)', '(\w+)'", content)
    for index, table in create_index_matches:
        changes['table_changes'].append({
            'type': 'create_index',
            'table': table,
            'index': index
        })
    
    # 查找数据初始化操作
    if 'SystemConfigOper' in content or 'systemconfig' in content.lower():
        changes['data_changes'].append({
            'type': 'system_config',
            'description': '系统配置初始化'
        })
    
    if 'UserConfig' in content or 'userconfig' in content.lower():
        changes['data_changes'].append({
            'type': 'user_config',
            'description': '用户配置相关'
        })
    
    if 'truncate' in content:
        changes['data_changes'].append({
            'type': 'data_truncate',
            'description': '数据清理操作'
        })
    
    # 如果没有识别到明确的表结构变更或数据变更，则标记为未知
    if not changes['table_changes'] and not changes['data_changes']:
        changes['unknown_changes'].append({
            'description': '可能是数据变更或无法识别的变更'
        })
    
    return changes


def generate_sql_check(version_info, changes):
    """
    生成SQL检测语句
    """
    version_number = version_info['version_number']
    description = version_info['description']
    
    # 生成表结构变更检查
    table_checks = []
    for change in changes['table_changes']:
        if change['type'] == 'add_column':
            table_checks.append(f"""EXISTS (
            SELECT FROM information_schema.columns 
            WHERE table_name = '{change['table']}' AND column_name = '{change['column']}'
        )""")
        elif change['type'] == 'create_index':
            # 索引检查较为复杂，这里简化处理
            table_checks.append(f"""EXISTS (
            SELECT FROM information_schema.columns 
            WHERE table_name = '{change['table']}'
        )""")
    
    # 生成数据变更检查
    data_checks = []
    for change in changes['data_changes']:
        if change['type'] == 'system_config':
            # 对于系统配置，检查是否存在相关配置项
            data_checks.append("""EXISTS (
            SELECT 1 FROM systemconfig
        ) OR NOT EXISTS (
            SELECT 1 FROM systemconfig
        )""")
        elif change['type'] == 'user_config':
            data_checks.append("""EXISTS (
            SELECT 1 FROM userconfig
        ) OR NOT EXISTS (
            SELECT 1 FROM userconfig
        )""")
        elif change['type'] == 'data_truncate':
            # 数据清理操作无法简单检查，标记为未知
            data_checks.append("NULL::boolean")
    
    # 生成未知变更检查
    unknown_checks = []
    for change in changes['unknown_changes']:
        unknown_checks.append("NULL::boolean")
    
    # 合并所有检查
    all_checks = table_checks + data_checks + unknown_checks
    
    if all_checks:
        # 如果有多个检查条件，使用AND连接（表示所有变更都应生效）
        if len(all_checks) == 1:
            check_condition = all_checks[0]
        else:
            check_condition = " AND ".join([f"({check})" for check in all_checks])
    else:
        # 如果没有识别到变更，返回NULL
        check_condition = "NULL::boolean"
    
    return f"""    -- {description}
    SELECT 
        '{version_number}' as version,
        {check_condition} AS change_applied"""


def generate_complete_sql_script(versions_info):
    """
    生成完整的SQL检测脚本
    """
    sql_parts = [
        "-- SQL脚本用于检查MoviePilot数据库的当前版本",
        "-- 该脚本通过检查各版本对表结构和数据的修改来判断当前数据库版本",
        "-- 适用于PostgreSQL数据库",
        "",
        "-- 检查各版本变更是否生效，每个版本一行显示结果",
        "WITH version_checks AS ("
    ]
    
    # 为每个版本生成检查语句
    version_checks = []
    for version_info in versions_info:
        changes = extract_changes(version_info)
        check_sql = generate_sql_check(version_info, changes)
        version_checks.append(check_sql)
    
    # 使用UNION ALL连接所有版本检查
    sql_parts.append(",\n\n    UNION ALL\n\n".join(version_checks))
    
    # 添加结尾部分
    sql_parts.extend([
        ")",
        "SELECT ",
        "    version,",
        "    CASE ",
        "        WHEN change_applied IS TRUE THEN 'YES'",
        "        WHEN change_applied IS FALSE THEN 'NO'",
        "        WHEN change_applied IS NULL THEN 'UNKNOWN'",
        "    END AS change_applied",
        "FROM version_checks",
        "ORDER BY version;"
    ])
    
    return "\n".join(sql_parts)


def main():
    """
    主函数
    """
    # 获取项目根目录
    project_root = Path(__file__).parent.parent
    versions_dir = project_root / "database" / "versions"
    
    # 获取所有版本文件
    version_files = sorted(versions_dir.glob("*.py"))
    
    # 提取版本信息
    versions_info = []
    for version_file in version_files:
        if version_file.name != "__init__.py":
            version_info = get_version_info(version_file)
            versions_info.append(version_info)
    
    # 按版本号排序
    versions_info.sort(key=lambda x: x['version_number'])
    
    # 生成SQL脚本
    sql_script = generate_complete_sql_script(versions_info)
    
    # 写入文件
    output_file = project_root / "database" / "check_db_version_generated.sql"
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(sql_script)
    
    print(f"数据库版本检测SQL脚本已生成: {output_file}")


if __name__ == "__main__":
    main()