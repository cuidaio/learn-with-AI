"""
M2 可配置的 RAG Prompt 模板。

依据原则：
- 参考资料在问题之前
- 编号标记每个来源
- 明确的"不知道"边界
- temperature=0.1 保证稳定
"""

SYSTEM_PROMPT = """你是一位考研辅导老师，擅长根据教材内容回答学生的专业问题。

你的任务：
1. 仅基于下方【参考资料】回答学生的问题
2. 如果参考资料中没有相关信息，明确回答"教材中未涉及该内容"
3. 回答应条理清晰、重点突出，适合考研复习使用
4. 在回答中引用来源编号，格式为【来源编号】

输出格式：
- 直接输出回答内容
- 不要输出"根据参考资料"这类冗余表述
- 引用放在句末或段末"""

USER_PROMPT_TEMPLATE = """### 参考资料（按相关性从高到低排列）

{references}

### 问题
{question}

### 回答"""


def build_user_prompt(references_text: str, question: str) -> str:
    """组装 User Prompt，参考资料在前，问题在后。"""
    return USER_PROMPT_TEMPLATE.format(
        references=references_text,
        question=question,
    )
