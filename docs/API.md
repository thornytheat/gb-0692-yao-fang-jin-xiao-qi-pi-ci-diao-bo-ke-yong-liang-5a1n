# 接口

`POST /api/run`：JSON中的csv文本，省略使用样例；或multipart字段file。最大5MB。

`POST /api/m1`至`POST /api/m7`：独立运行到指定模块，JSON结构同运行接口。

`GET /api/history`：历史批次。`POST /api/review`接收id、revision和decision（通过或退回）。`GET /api/evidence.csv`提供单一证据导出。

结构错误422，版本变化409，文件过大413；错误返回code与message。所有页面可从左侧七个模块入口访问。

`GET /api/runs/<id>`读取指定批次；页面与证据CSV通过run_id查询参数绑定批次，模块导航保留该参数。

JSON请求体必须是对象，数组、标量、null、损坏JSON及错误上传字段返回400，且不运行默认样例。

## 夜班放行

`GET /release`：放行页面，按run_id绑定批次，调拨单取自该批次M5分配结果，首次访问时按确定顺序建档。

`GET /api/release/orders?run_id=`：每单放行结论。状态为待首签、待补签（有条件放行）、已放行、被拦下（终态）；含首签/补签人、时间、晚到标记与乐观锁version。

`GET /api/release/ledger?run_id=`：签核档案流水，只增不删。

`POST /api/release/sign`：JSON字段run_id、order_id、action、pharmacist、action_id、version，可选at（ISO时间，缺省取当前UTC）。action为首签通过、首签驳回、补签通过、补签驳回、撤回首签、撤回补签。补签人与首签人相同返回422（code=DUAL）；撤回非本人返回422（code=WITHDRAW）；状态不允许该动作或version陈旧返回409，旧版放行结论不变。action_id为幂等键：同一action_id重复提交返回首次结论且replayed=true，不新增签核。补签晚于首签12小时（COUNTERSIGN_GRACE_HOURS）记late=true，仍正常流转。
