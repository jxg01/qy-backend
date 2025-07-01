from sqlalchemy import create_engine, text


def get_db_conn_url(db_env):
    return f"mysql+pymysql://{db_env['username']}:{db_env['password']}@{db_env['host']}:{db_env['port']}/{db_env['name']}"
    # if db_env.db_type == 'mysql':
    #     return f"mysql+pymysql://{db_env.username}:{db_env.password}@{db_env.host}:{db_env.port}/{db_env.name}"
    # elif db_env.db_type == 'postgres':
    #     return f"postgresql://{db_env.username}:{db_env.password}@{db_env.host}:{db_env.port}/{db_env.name}"
    # # 可扩展更多类型
    # raise ValueError('暂不支持的数据库类型')


def execute_sql_dynamic(db_env, sql, variables: dict = None):
    try:
        url = get_db_conn_url(db_env)
        engine = create_engine(url)
        if variables:
            sql = sql.format(**variables)
        with engine.connect() as conn:
            result = conn.execute(text(sql))
            if sql.strip().lower().startswith('select'):
                # Get column information
                columns = result.keys()
                # Convert to a list of dictionaries
                return [dict(zip(columns, row)) for row in result]
            else:
                return {'status': 'success', 'affected_rows': result.rowcount}
    except Exception as e:
        return {'status': 'error', 'message': str(e)}


if __name__ == '__main__':
    # 示例数据库环境配置
    class MockDBEnv:
        db_type = 'mysql'
        username = 'root'
        password = '12345678'
        host = '127.0.0.1'
        port = 3306
        # name = 'easy_api'
        name = 'test_db'

    # db_envs = MockDBEnv()
    print(MockDBEnv())

    db_envs = {'username': 'acc', 'name': 'easy_api', 'host': '127.0.0.1', 'port': 3306, 'password': '12345678'}
    # 示例 SQL 语句
    # sql_query = "SELECT * FROM qy_case_execution WHERE id = {age};"
    sql_update = "UPDATE users SET is_staff=1 WHERE id = {age};"
    variables1 = {'age': 1}

    # 执行 SQL
    results = execute_sql_dynamic(db_envs, sql_update, variables1)
    print(results)
    if results:
        print(123)

