# False Negative Analysis

本轮正式结果为 **FN = 0 / 5**，因此没有可逐例分析的 false negative。

这只说明模型识别了本轮目的性选择的 5 个清晰 positive，不能推出模型不会在更隐蔽的跨文件 call graph、编译配置、隐式 state 或复杂 input-construction 案例上漏报。剩余 8 个 confirmed degradation events 在本阶段未生成 case、未放入 prompt、未用于调参，也未参与本轮预测；它们才是下一阶段检验 FN 的独立材料。

为了保持 hold-out 独立性，不应根据那 8 个事件的具体机制补写规则。下一阶段应先依据本轮已经观察到的问题冻结：

- target-scope 定义；
- context selection 规则；
- YES 所需的反事实证据格式；
- 动态 changed-path reachability 验证协议；
- 一次调用、无选择性重试的执行规则。

在此之后再一次性解封并运行 8 个 hold-out positive。
