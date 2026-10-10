# Day 6:Action客户端
2026.8.17

把要发送的goal自定义位send-goal，然后把需要发送的参数都放在send_goal_options中。

这个auto是占位的，因为这里原本是goal-handle，但这里不需要关注这个参数，就用auto代替。
send_goal_options.feedback_callback = 
[node](auto, const std::shared_ptr<const Fibonacci::Feedback> feedback)

这里是流插运算符
含义：把右边的数据，塞到左边的流对象中
类比：就像把水倒进杯子，这里是把 num 的文本形式“倒进” ss 这个“杯子”里
ss << num << " "
先执行 ss << num：把数字（比如 5）转换成字符串 "5"，追加到 ss 内部的末尾。这个操作完成后，会返回 ss 对象本身（的引用）。
再执行 (ss返回的对象) << " "：把空格字符串 " " 追加到刚才那个 "5" 的后面

ss.str().c_str()
而是“连续调用两个函数”，这叫作链式调用（Method Chaining）
这是调用 std::stringstream 对象的 str() 成员函数。
作用：把流 ss 内部缓冲区的所有内容，提取出来，生成一个临时的 std::string 对象（即标准 C++ 字符串）。
这是调用上一步那个临时 std::string 对象的 c_str() 成员函数。
作用：返回一个 const char* 类型的指针（即 C 语言风格的字符串，末尾带 \0）。
类比：这就像给那个瓶子贴上一个“纯文本”的标签，让 C 语言函数能看懂它
原因：RCLCPP_INFO 使用的是 printf 风格的格式化字符串，其中 %s 占位符只接受 const char*（C 风格字符串）

问题：
feedback->partial_sequence例程中使用的2这个，但是实际上应该是sequence

auto goal = std::make_shared<example_interfaces::action::Fibonacci::Goal>();
// ... 
client->async_send_goal(goal, send_goal_options);  // ❌ 传入 shared_ptr
但API期望：
client->async_send_goal(goal, send_goal_options);  // 其中 goal 是 Goal 对象，不是指针
修改方向：1：
把 goal 定义成普通对象，而非智能指针：
// 3. 构造目标（Goal）
example_interfaces::action::Fibonacci::Goal goal;  // 注意不是指针
goal.order = 10;
// 5. 异步发送目标（直接传对象）
client->async_send_goal(goal, send_goal_options);
2：client->async_send_goal(*goal, send_goal_options);  // 注意星号，使用*goal解引用