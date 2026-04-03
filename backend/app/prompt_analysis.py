import os
import re
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

try:
    import dashscope
except ImportError:  # pragma: no cover
    dashscope = None


load_dotenv()

DASHSCOPE_BASE_HTTP_API_URL = os.getenv(
    "DASHSCOPE_BASE_HTTP_API_URL",
    "https://dashscope.aliyuncs.com/api/v1",
)
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY")
VIDEO_ANALYSIS_MODEL_NAME = os.getenv("MODEL_NAME", "qwen-vl-max-latest")
VIDEO_ANALYSIS_FPS = float(os.getenv("VIDEO_FPS", "2"))

if dashscope is not None:
    dashscope.base_http_api_url = DASHSCOPE_BASE_HTTP_API_URL


DIRECTOR_PROMPT_TEMPLATE = """
请完整观看这个视频片段，并直接输出一条可交给视频生成 AI 使用的导演式成片提示词。

只输出最终提示词正文，不要输出 JSON，不要输出 Markdown 代码块，不要解释你在做什么，不要写成字段清单式报告。
整体必须是一条自然、连续、可直接阅读和修改的长文本提示词。

请尽量保留视频本身的镜头语言、动作推进、关系变化、情绪转折、声音层次、光线质感和视觉锚点。
如果有台词、旁白、环境声、音乐、动作音，请融入提示词描述。
如果某些信息无法确定，不要编造具体专有信息，可以写保持与原视频相近的感觉。
结尾请补一小段生成注意事项，提醒模型不要做错关键细节。
""".strip()


def extract_response_text(response) -> str:
    try:
        content = response.output.choices[0].message.content
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(f"无法从响应中提取正文: {response}") from exc

    if isinstance(content, str):
        return content.strip()

    if isinstance(content, list):
        text_parts = []
        for item in content:
            if isinstance(item, dict) and "text" in item:
                text_parts.append(str(item["text"]))
            elif isinstance(item, str):
                text_parts.append(item)

        joined_text = "\n".join(part.strip() for part in text_parts if str(part).strip())
        if joined_text:
            return joined_text

    raise RuntimeError(f"响应正文结构不符合预期: {content}")


def clean_model_output(text: str) -> str:
    cleaned_text = text.strip()
    if cleaned_text.startswith("```"):
        cleaned_text = re.sub(
            r"^```(?:text|markdown)?",
            "",
            cleaned_text,
            flags=re.IGNORECASE,
        ).strip()
        cleaned_text = re.sub(r"```$", "", cleaned_text).strip()
    return cleaned_text


def call_multimodal(messages: list[dict]) -> str:
    if dashscope is None:
        raise RuntimeError("dashscope 依赖未安装。")
    if not DASHSCOPE_API_KEY:
        raise RuntimeError("缺少环境变量 DASHSCOPE_API_KEY。")
    if not VIDEO_ANALYSIS_MODEL_NAME:
        raise RuntimeError("缺少环境变量 MODEL_NAME。")

    call_kwargs = {
        "api_key": DASHSCOPE_API_KEY,
        "model": VIDEO_ANALYSIS_MODEL_NAME,
        "messages": messages,
        "result_format": "message",
    }

    try:
        response = dashscope.MultiModalConversation.call(**call_kwargs)
    except TypeError:
        call_kwargs.pop("result_format", None)
        response = dashscope.MultiModalConversation.call(**call_kwargs)

    if getattr(response, "status_code", None) != 200:
        raise RuntimeError(f"调用失败: {response}")

    return clean_model_output(extract_response_text(response))


def analyze_segment_prompt(segment: dict, append_log) -> dict:
    segment_path = Path(segment["export_file_path"]).resolve()
    append_log("info", f"开始分析片段 group_{segment['group_index']:03d}")

    messages = [
        {
            "role": "user",
            "content": [
                {"video": f"file://{segment_path}", "fps": VIDEO_ANALYSIS_FPS},
                {"text": DIRECTOR_PROMPT_TEMPLATE},
            ],
        }
    ]

    prompt_text = call_multimodal(messages)
    append_log("success", f"片段 group_{segment['group_index']:03d} 提示词生成完成")

    return {
        "prompt": prompt_text,
        "model": VIDEO_ANALYSIS_MODEL_NAME,
        "fps": VIDEO_ANALYSIS_FPS,
        "generated_at": datetime.utcnow().isoformat(),
    }


def can_run_prompt_analysis() -> bool:
    return bool(DASHSCOPE_API_KEY and VIDEO_ANALYSIS_MODEL_NAME and dashscope is not None)
