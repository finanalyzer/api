# 持仓管理与交易记录管理 - 实现计划

## [x] 任务 1：创建数据库模型和表结构
- **优先级**：P0
- **依赖**：None
- **描述**：
  - 创建自选股表（portfolio_stocks）和交易记录表（transactions）的数据库模型
  - 实现表结构，包括所有必要的字段和约束
  - 添加索引以优化查询性能
- **验收标准**：AC-1, AC-6, AC-14
- **测试要求**：
  - `programmatic` TR-1.1：数据库表结构创建成功，包含所有必要字段
  - `programmatic` TR-1.2：索引创建成功，优化查询性能
- **备注**：使用SQLite数据库，遵循现有项目的数据库管理模式

## [x] 任务 2：实现自选股管理的CRUD操作
- **优先级**：P0
- **依赖**：任务 1
- **描述**：
  - 实现自选股的创建、读取、更新、删除功能
  - 实现按股票代码查询单个自选股详情
  - 实现获取全部自选股列表
- **验收标准**：AC-1, AC-2, AC-3, AC-4, AC-5, AC-16
- **测试要求**：
  - `programmatic` TR-2.1：GET /api/v1/portfolio/stocks返回所有自选股列表
  - `programmatic` TR-2.2：GET /api/v1/portfolio/stocks/{symbol}返回指定股票详情
  - `programmatic` TR-2.3：POST /api/v1/portfolio/stocks成功创建新自选股
  - `programmatic` TR-2.4：PUT /api/v1/portfolio/stocks/{symbol}成功更新自选股信息
  - `programmatic` TR-2.5：DELETE /api/v1/portfolio/stocks/{symbol}成功删除自选股
  - `programmatic` TR-2.6：无持仓时，持仓相关字段显示为零值
- **备注**：确保数据验证和错误处理

## [x] 任务 3：实现交易记录管理的CRUD操作
- **优先级**：P0
- **依赖**：任务 1, 任务 2
- **描述**：
  - 实现交易记录的创建、读取、更新、删除功能
  - 实现按股票代码查询交易记录
  - 实现按日期范围查询交易记录
- **验收标准**：AC-6, AC-7, AC-8, AC-9, AC-10, AC-11
- **测试要求**：
  - `programmatic` TR-3.1：GET /api/v1/portfolio/transactions返回所有交易记录
  - `programmatic` TR-3.2：GET /api/v1/portfolio/transactions?symbol={symbol}返回指定股票交易记录
  - `programmatic` TR-3.3：GET /api/v1/portfolio/transactions?start_date={start}&end_date={end}返回指定日期范围交易记录
  - `programmatic` TR-3.4：POST /api/v1/portfolio/transactions成功创建新交易记录
  - `programmatic` TR-3.5：PUT /api/v1/portfolio/transactions/{id}成功更新交易记录
  - `programmatic` TR-3.6：DELETE /api/v1/portfolio/transactions/{id}成功删除交易记录
- **备注**：确保交易记录操作与持仓数据更新的事务处理

## [x] 任务 4：实现持仓数据计算逻辑
- **优先级**：P0
- **依赖**：任务 1, 任务 2
- **描述**：
  - 实现加权平均法计算持仓均价
  - 实现持有数量的计算
  - 实现市值总计的计算
  - 实现卖出交易时的数量验证（不超过当前持有数量）
- **验收标准**：AC-12, AC-13
- **测试要求**：
  - `programmatic` TR-4.1：买入交易后，持有数量增加，持仓均价正确计算
  - `programmatic` TR-4.2：卖出交易后，持有数量减少，持仓均价正确计算
  - `programmatic` TR-4.3：卖出数量超过当前持有数量时，返回错误
  - `programmatic` TR-4.4：市值总计正确计算（持仓均价×持有数量）
- **备注**：使用加权平均法计算持仓均价

## [x] 任务 5：实现交易记录与持仓数据的同步
- **优先级**：P0
- **依赖**：任务 3, 任务 4
- **描述**：
  - 实现交易记录创建后自动更新对应自选股的持仓数据
  - 实现交易记录更新后重新计算对应自选股的持仓数据
  - 实现交易记录删除后重新计算对应自选股的持仓数据
  - 确保所有操作的事务性
- **验收标准**：AC-9, AC-10, AC-11, AC-14
- **测试要求**：
  - `programmatic` TR-5.1：创建交易记录后，对应自选股的持仓数据正确更新
  - `programmatic` TR-5.2：更新交易记录后，对应自选股的持仓数据重新计算
  - `programmatic` TR-5.3：删除交易记录后，对应自选股的持仓数据重新计算
  - `programmatic` TR-5.4：所有操作保持事务一致性
- **备注**：使用数据库事务确保操作的原子性

## [x] 任务 6：实现数据一致性校验接口
- **优先级**：P1
- **依赖**：任务 3, 任务 5
- **描述**：
  - 实现GET /api/v1/portfolio/validate接口
  - 验证持仓数据与交易记录的一致性
  - 返回验证结果和不一致的详情
- **验收标准**：AC-15
- **测试要求**：
  - `programmatic` TR-6.1：GET /api/v1/portfolio/validate返回持仓数据与交易记录的一致性验证结果
  - `programmatic` TR-6.2：当数据不一致时，返回详细的不一致信息
- **备注**：验证逻辑应遍历所有自选股，重新计算持仓数据并与当前数据比较

## [x] 任务 7：添加API路由和文档
- **优先级**：P1
- **依赖**：任务 2, 任务 3, 任务 6
- **描述**：
  - 在FastAPI应用中添加portfolio相关的API路由
  - 确保所有接口符合RESTful规范
  - 生成完整的OpenAPI文档
- **验收标准**：AC-1, AC-2, AC-3, AC-4, AC-5, AC-6, AC-7, AC-8, AC-9, AC-10, AC-11, AC-15
- **测试要求**：
  - `programmatic` TR-7.1：所有API路由正确注册
  - `human-judgment` TR-7.2：API文档完整且符合RESTful规范
- **备注**：遵循现有项目的路由注册方式

## [x] 任务 8：添加数据验证和错误处理
- **优先级**：P1
- **依赖**：任务 2, 任务 3, 任务 4
- **描述**：
  - 为所有输入数据添加类型验证
  - 为所有业务规则添加验证（如卖出数量限制）
  - 实现统一的错误处理机制
  - 提供清晰的错误信息和适当的HTTP状态码
- **验收标准**：FR-11, NFR-3, NFR-4
- **测试要求**：
  - `programmatic` TR-8.1：无效输入数据返回400错误
  - `programmatic` TR-8.2：卖出数量超过持有数量返回400错误
  - `programmatic` TR-8.3：错误信息清晰明确
- **备注**：使用Pydantic进行数据验证

## [x] 任务 9：编写单元测试
- **优先级**：P1
- **依赖**：任务 2, 任务 3, 任务 4, 任务 5, 任务 6
- **描述**：
  - 为自选股管理功能编写单元测试
  - 为交易记录管理功能编写单元测试
  - 为持仓数据计算功能编写单元测试
  - 为数据一致性校验功能编写单元测试
- **验收标准**：所有验收标准
- **测试要求**：
  - `programmatic` TR-9.1：所有单元测试通过
  - `programmatic` TR-9.2：测试覆盖率达到80%以上
- **备注**：使用pytest框架编写测试

## [x] 任务 10：集成和测试
- **优先级**：P1
- **依赖**：任务 7, 任务 8, 任务 9
- **描述**：
  - 集成所有模块
  - 运行完整的测试套件
  - 验证所有功能正常工作
  - 测试API响应时间和性能
- **验收标准**：所有验收标准, NFR-1
- **测试要求**：
  - `programmatic` TR-10.1：所有测试通过
  - `programmatic` TR-10.2：API响应时间符合要求
  - `human-judgment` TR-10.3：系统整体功能正常
- **备注**：确保所有功能集成后正常工作