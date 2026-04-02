import os
import random
import re
import shutil
import subprocess
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from queue import Queue
from threading import Lock
from typing import Dict, List, Optional, Tuple
from urllib.parse import quote
from uuid import uuid4

import dashscope
from dotenv import load_dotenv
from scenedetect import ContentDetector, SceneManager, open_video
from scenedetect.video_splitter import split_video_ffmpeg

load_dotenv()

MIN_GROUP_DURATION_SECONDS = 6.0
MAX_GROUP_DURATION_SECONDS = 14.0
MAX_GROUPING_SOLUTIONS = 2376

dashscope.base_http_api_url = os.getenv("DASHSCOPE_BASE_HTTP_API_URL")
VIDEO_ANALYSIS_MODEL_NAME = os.getenv("MODEL_NAME")
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY")
VIDEO_ANALYSIS_FPS = float(os.getenv("VIDEO_FPS"))

DIRECTOR_PROMPT_TEMPLATE = """
请完整观看这个视频，并直接输出一条可交给视频生成AI使用的“导演式成片提示词”。

你的目标不是做摘要，也不是做分析报告，而是把这条视频尽可能还原成一段完整、连贯、可直接用于生成的视频说明。输出内容要像导演在向生成模型详细描述整条视频：画面里到底出现了什么，主体在什么环境下以什么状态做了什么，动作、关系、情绪、声音、镜头和节奏是如何一步一步变化的，哪些细节必须保留，哪些变化不能丢。

输出硬性要求:
1. 只输出最终提示词正文
2. 不要输出JSON
3. 不要输出Markdown代码块
4. 不要解释你在做什么
5. 不要写成字段清单式报告
6. 整体必须是一条自然、连续、可直接阅读和修改的长文本提示词
7. 不要预设题材，必须完全根据视频本身来写，适用于剧情、广告、口播、人物、动物、食物、风景、产品展示等任意视频
8. 除视频中实际说出的话、旁白原话、以及确实属于画面内容本身的可见文字原文外，其他所有描述一律使用中文。对于仅用于表达对白、口播、旁白内容的字幕，不要描述为画面上出现的文字，而要转写为对应人物或旁白说的话、语气、停顿和情绪状态
9. 如果某些信息无法明确判断，不要编造具体专有信息，可以写“保持与原视频相近的感觉”“呈现与原视频相近的状态”“音色接近原视频中的听感”
10. 在保证完整的前提下，少写空泛修饰词，优先保留真正影响生成结果的细节
11. 重点不是只写“画面里有什么”，而是要写“这些内容是如何出现、如何变化、如何推进、如何相互影响的”
12. 不要只写静态描述，要把视频作为一个连续发生的视听过程来重建
13. 要尽量保留视频本身的节奏、关系推进、情绪转折、动作因果和声音层次
14. 对于人物、动作、关系、声音、镜头、节奏、光线、质感等，会影响最终生成效果的细节，尽可能写得更细
15. 如果视频里有多段变化、多次转折、多组主体互动、多次说话或多次情绪变化，都要尽量按顺序写出来
16. 结尾必须补一小段“生成注意事项”，结合这条视频本身提醒模型不要做错关键细节

你输出的这条提示词，必须尽可能自然融合并覆盖以下层面:

一. 成片目标与整体感受
要先交代这条视频整体想让观众感受到什么，是压迫、温柔、紧张、克制、暧昧、治愈、危险、孤独、热烈、悲伤、兴奋、爽感、纪实感、广告感、情绪冲突还是别的感觉。要写清这条视频最核心的观看重点是什么，是人物关系、产品展示、动作过程、情绪爆发、环境氛围、口播信息还是其他重点。还要说明整条视频的整体观看路径是如何推进的，是先建立环境，再推进动作，再推高情绪，还是先给冲击点，再补足信息，还是持续堆高张力。

二. 场景与环境细节
要写清楚视频发生在什么环境里，空间是什么样的，场景大小感、封闭感或开阔感如何，背景里有什么，前景、中景、后景分别有什么，主体和背景之间的关系如何。要尽量写清楚光线来自哪里，光是硬还是柔，是顶光、侧光、逆光、自然光、环境光还是混合光，整体偏冷还是偏暖，亮度高低如何，是否有局部高光、阴影压迫、轮廓光、反光、漫反射。要尽量写清空间陈设、家具、墙面、材质、地面、天气、时间感、空气感、烟雾感、潮湿感、灰尘感、风感、水汽感、布景密度、背景元素的存在感。场景如果发生变化，要写清楚从什么环境切到什么环境，变化前后视觉感受、情绪作用、空间关系有什么不同。

三. 主体、外观、体态与关系
要写清楚画面里出现了谁或什么，包括人数、性别、年龄感、物种、身份感、职业感、角色关系、主次关系、控制关系、依赖关系、对立关系、亲密关系或陌生关系。要尽量写清外观特征、脸型、五官、发型、肤色、体型、体态、站姿、坐姿、走姿、手部状态、肩颈状态、头部角度、眼神方向、视线落点、与他人距离、与镜头距离。服装要尽量写清颜色、款式、松紧、垂坠感、材质、纹理、光泽、褶皱状态、干净程度、正式感或生活感。配饰和道具要尽量写清类型、位置、大小感、金属感、塑料感、木质感、玻璃感、磨损感、使用痕迹。不是人物视频时，也要尽量写清主体的形态、大小、结构、材质、表面状态、颜色变化、运动状态和与环境的关系。

四. 初始状态与开场信息
要写清楚视频一开始先让观众看到什么，是先看到主体、先看到环境、先看到动作、先看到局势、先看到表情还是先听到声音。要写清开场时整体气氛是什么，主体一开始处于什么状态，谁占据主导，谁在观察，谁在等待，谁在压着情绪，谁在执行动作。要尽量写清开场第一眼最有辨识度的东西是什么，哪些元素一出现就决定了这条视频的感觉。

五. 动作过程、微动作与变化链条
这是最重要的部分。不要只写结果，要按视频推进顺序尽量细地写清楚发生了什么。要尽量写出:
谁先出现
谁先动
谁后动
谁在做主要动作
谁在看
谁在听
谁在靠近
谁在后退
谁在抬手
谁在放下
谁在转头
谁在低头
谁在抬眼
谁在停顿
谁在身体前倾
谁在避开
谁在握紧
谁在松开
谁在沉默
谁在说话
谁在听完后反应
谁的动作带来下一步变化
如果动作很细，也要尽量写出微动作，比如手指动作、呼吸变化、嘴角变化、眉眼变化、肩膀变化、下巴变化、步伐变化、视线转移、短暂停顿、迟疑、僵住、轻微靠近、轻微后仰、咬牙、闭眼、眨眼、吞咽、抿嘴、皱眉、放松、紧绷等。整条提示词要让人能感到这段视频是在一步一步发展，而不是只有几个结果点。

六. 情绪状态、情绪关系与情绪变化
不要只写“开心”“生气”“难过”这种标签，要尽量写清楚每个主体在不同阶段的情绪状态、隐藏情绪、外显情绪和变化过程。比如是表面冷静但内里压抑，是嘴硬但受伤，是强撑、克制、迟疑、抗拒、决绝、紧张、危险、轻蔑、委屈、心虚、试探、温柔、兴奋、羞怯、脆弱、愤怒、麻木、崩溃边缘。要写清谁的情绪先变，谁的情绪后变，谁在压迫，谁在被压迫，谁在主导气氛，谁在试图打破平衡。要尽量写出情绪的推进路径，而不是只给一个最终结论。

七. 台词、口播、旁白内容与说话方式
如果视频里有对白、口播、旁白，请尽量写清:
是谁说的
说了什么
是在什么情境下说的
说之前正在做什么
说的时候看向谁或朝向哪里
语速是快、慢、停顿明显还是连续不断
语气是冷、硬、压抑、克制、发颤、低声、坚定、命令式、试探式、疲惫、温柔、平静、愤怒、哽咽还是别的状态
说话时是否带呼吸感、气声、压着说、咬牙说、贴近说、远一点说、边做动作边说、说完后留空白
如果无法准确还原原话，可以概括说话内容，但要尽量保留说话场景、说话目的、说话对象、语气和情绪状态。若能明确识别原话，可保留原话原文。除非文字本身就是画面中的真实内容，例如招牌、包装、界面、聊天记录、海报、片头标题、产品文案等，否则不要写“屏幕出现字幕”“下方出现文字”“画面打出字幕”等描述，而要默认将这类内容还原成角色说话或旁白表达。

八. 声音、音色、环境音、动作音与音乐层次
如果视频里存在明显声音线索，要尽量写清:
谁的声音最重要
声音是近还是远
音色是偏厚、偏薄、偏轻、偏沉、偏年轻、偏成熟、偏冷、偏柔、偏尖、偏粗、偏沙、偏实还是别的听感
如果音色无法准确判断，不要乱编具体声线设定，可以写“保持与原视频相近的声音质感和情绪状态”
背景音乐是什么感觉，节奏是慢、紧、压抑、舒缓、热烈、悬疑、轻快、悲伤还是别的状态
环境音有哪些，动作音有哪些，是否有脚步、呼吸、衣料摩擦、碰撞、机械声、水声、风声、纸张声、键盘声、门声、动物声、人群声、室内空响、回声、交通声、餐具声等
对白和音乐谁为主谁为辅
什么时候音乐该抬起
什么时候音乐该压下去
什么时候应该留安静
什么时候动作音或呼吸声更重要
如果声音变化本身推动了情绪，也要把这种推动写出来。

九. 镜头、构图、画面组织与节奏推进
不要只堆砌“特写”“中景”“推镜”这些术语，要尽量写清镜头为什么这么走、画面怎么跟着内容变化。要尽量描述:
开头是先交代整体还是直接贴近主体
什么时候先看场景
什么时候看人物关系
什么时候看动作细节
什么时候看表情
什么时候看反应
什么时候切换主体
什么时候切换空间
画面是稳的、轻微晃动的、跟随的、推进的、后拉的、平移的还是静止停住的
构图是压迫的、对峙的、对称的、偏置的、拥挤的、留白的还是集中视线的
景别、角度、距离、遮挡关系、前后层次有没有明显变化
转场是动作推动、情绪推动、节奏推动、信息推动还是生硬切换
节奏是持续推进、逐步堆高、先慢后快、先快后停、突然打断还是层层累积
如果视频明显依赖某种镜头顺序、景别变化或节奏切换来推动情绪，一定要写出来。

十. 关键识别点、决定性细节与不能丢的变化
要尽量找出哪些内容是一变就不像原视频的关键，比如:
某个特定动作
某个表情瞬间
某个说话状态
某句关键台词
某个视线关系
某种情绪推进方式
某个构图关系
某个场景元素
某个道具状态
某个节奏拐点
某个声音瞬间
某个镜头与动作的配合
这些内容不要机械列清单，而是自然地写进提示词里，作为必须保留的核心辨识点。

十一. 风格、质感、真实度与生成方向
要写清楚整体更偏电影感、纪实感、广告感、短剧感、写实感、生活化、商业化、情绪化、梦幻感、锐利感、柔和感还是其他质感。要尽量写清画面色彩、对比、锐度、清晰度、材质还原、皮肤状态、织物表现、金属反光、玻璃质感、食物质感、动物毛发、液体状态、景深、颗粒感、真实度、人工感强弱、镜头真实感。要尽量写清哪些视觉质感对这条视频特别重要。

十二. 生成注意事项
在结尾补一小段自然语言形式的生成注意事项，必须结合这条视频本身提醒:
不要丢失关键动作和关键情绪变化
不要把人物关系和强弱状态做错
不要让台词、语气、口型、情绪不匹配
不要让动作断裂、反应不连贯、表情跳变
不要让场景、服装、道具、站位、光线、材质在前后镜头里突然不合理变化
不要让画面崩坏、人物失真、材质错误、声音不稳、音画不同步
但不要写成空泛模板，要让这些注意事项看起来就是针对这条视频本身的。

写作方式要求:
1. 整条提示词要像在把这条视频从头到尾重新讲一遍，同时又是在指导模型如何生成
2. 可以自然分段，但整体仍然必须是一条完整的“导演式总提示词”
3. 优先写动态变化、关系变化、情绪变化、动作变化、声音变化、镜头变化
4. 不是只描述静态画面，而是要把视频作为一个连续发生的视听过程来写
5. 除实际说出的话或原字幕原文外，其余描述全部使用中文
""".strip()


@dataclass
class LogEntry:
    timestamp: str
    level: str
    video_name: Optional[str]
    message: str


@dataclass
class VideoProcessResult:
    video_name: str
    status: str
    error_message: Optional[str] = None
    original_scenes: List[dict] = field(default_factory=list)
    merged_segments: List[dict] = field(default_factory=list)
    chosen_grouping_plan: List[List[int]] = field(default_factory=list)
    summary: dict = field(default_factory=dict)
    logs: List[dict] = field(default_factory=list)
    analysis_status: str = "idle"


@dataclass
class TaskState:
    task_id: str
    total_videos: int
    completed_videos: int = 0
    status: str = "processing"
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    task_logs: List[dict] = field(default_factory=list)
    video_results: List[dict] = field(default_factory=list)
    event_queue: Queue = field(default_factory=Queue)


class TaskStore:
    """Thread-safe in-memory task registry for this demo."""

    def __init__(self) -> None:
        self._tasks: Dict[str, TaskState] = {}
        self._lock = Lock()

    def create_task(self, total_videos: int) -> TaskState:
        with self._lock:
            task_id = str(uuid4())
            task = TaskState(task_id=task_id, total_videos=total_videos)
            self._tasks[task_id] = task
            return task

    def get_task(self, task_id: str) -> Optional[TaskState]:
        with self._lock:
            return self._tasks.get(task_id)


def make_log(level: str, message: str, video_name: Optional[str] = None) -> dict:
    return asdict(LogEntry(
        timestamp=datetime.utcnow().isoformat(),
        level=level,
        video_name=video_name,
        message=message,
    ))


def build_media_url(base_public_url: str, data_root: Path, file_path: Path) -> str:
    """
    Build a browser-playable URL from a real file path under backend/data.

    The Flask media route serves files from DATA_ROOT, so preview URLs must keep the
    `tasks/<task_id>/...` prefix. Without that prefix the browser requests the wrong path
    and the merged preview clip returns 404 even though the file actually exists on disk.
    """

    relative_path = file_path.relative_to(data_root).as_posix()
    return f"{base_public_url}/media/{quote(relative_path, safe='/')}"


def extract_response_text(response) -> str:
    try:
        content = response.output.choices[0].message.content
    except Exception as exc:  # pragma: no cover - depends on SDK response shape
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


def call_multimodal(messages: List[dict]) -> str:
    if dashscope is None:
        raise RuntimeError("dashscope 依赖未安装。")
    if not DASHSCOPE_API_KEY:
        raise RuntimeError("缺少环境变量 DASHSCOPE_API_KEY。")
    if not VIDEO_ANALYSIS_MODEL_NAME:
        raise RuntimeError("缺少环境变量 MODEL_NAME。")

    call_kwargs: Dict[str, object] = {
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
                {
                    "video": f"file://{segment_path}",
                    "fps": VIDEO_ANALYSIS_FPS,
                },
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


def detect_and_split_original_scenes(
        source_video_path: Path,
        scene_output_directory: Path,
        base_public_url: str,
        video_name: str,
        append_log,
) -> List[dict]:
    """Detect scenes and use PySceneDetect's ffmpeg splitter to create real scene files."""
    append_log("info", f"Starting scene detection for video: {video_name}")
    data_root = scene_output_directory.parents[3]

    video_stream = open_video(str(source_video_path))
    scene_manager = SceneManager()
    scene_manager.add_detector(ContentDetector())
    scene_manager.detect_scenes(video=video_stream)
    detected_scenes = scene_manager.get_scene_list(start_in_scene=True)

    if not detected_scenes:
        raise RuntimeError("No scenes were detected by PySceneDetect.")

    scene_output_directory.mkdir(parents=True, exist_ok=True)
    append_log("info", f"Detected {len(detected_scenes)} scenes. Starting built-in split operation.")

    split_video_ffmpeg(
        input_video_path=str(source_video_path),
        scene_list=detected_scenes,
        output_dir=scene_output_directory,
        show_progress=False,
    )

    exported_scene_files = sorted(scene_output_directory.glob("*.mp4"))
    if len(exported_scene_files) != len(detected_scenes):
        raise RuntimeError(
            f"Split result mismatch: detected={len(detected_scenes)}, exported={len(exported_scene_files)}"
        )

    original_scenes: List[dict] = []
    for index, ((start_timecode, end_timecode), scene_file_path) in enumerate(
            zip(detected_scenes, exported_scene_files),
            start=1,
    ):
        start_seconds = start_timecode.get_seconds()
        end_seconds = end_timecode.get_seconds()
        duration_seconds = end_seconds - start_seconds
        original_scenes.append(
            {
                "scene_index": index,
                "start_seconds": start_seconds,
                "end_seconds": end_seconds,
                "duration_seconds": duration_seconds,
                "file_path": str(scene_file_path),
                "public_url": build_media_url(base_public_url, data_root, scene_file_path),
            }
        )

    append_log("success", f"Scene split finished. Exported {len(original_scenes)} original scene files.")
    return original_scenes


def search_valid_continuous_groupings(original_scenes: List[dict], append_log) -> Tuple[List[List[List[int]]], bool]:
    append_log("info", "DFS grouping search started.")
    durations = [scene["duration_seconds"] for scene in original_scenes]

    if any(duration > MAX_GROUP_DURATION_SECONDS for duration in durations):
        raise RuntimeError("At least one original scene is longer than 14 seconds, no valid grouping exists.")

    total_duration = sum(durations)
    min_groups = int(total_duration // MAX_GROUP_DURATION_SECONDS)
    max_groups = int(total_duration // MIN_GROUP_DURATION_SECONDS) + 1
    if min_groups > max_groups:
        raise RuntimeError("Total duration cannot be partitioned into contiguous groups of 6-14 seconds.")

    n = len(durations)
    suffix_sum = [0.0] * (n + 1)
    for i in range(n - 1, -1, -1):
        suffix_sum[i] = suffix_sum[i + 1] + durations[i]

    solutions: List[List[List[int]]] = []
    hit_limit = False

    def dfs(start_index: int, plan: List[List[int]]) -> None:
        nonlocal hit_limit
        if hit_limit:
            return
        if start_index == n:
            solutions.append([group[:] for group in plan])
            if len(solutions) >= MAX_GROUPING_SOLUTIONS:
                hit_limit = True
            return

        remaining_duration = suffix_sum[start_index]
        if remaining_duration < MIN_GROUP_DURATION_SECONDS:
            return

        current_duration = 0.0
        current_group: List[int] = []
        for end_index in range(start_index, n):
            current_duration += durations[end_index]
            current_group.append(end_index + 1)

            if current_duration > MAX_GROUP_DURATION_SECONDS:
                break

            if current_duration >= MIN_GROUP_DURATION_SECONDS:
                next_start = end_index + 1
                remaining = suffix_sum[next_start]
                if 0 < remaining < MIN_GROUP_DURATION_SECONDS:
                    continue
                plan.append(current_group[:])
                dfs(next_start, plan)
                plan.pop()
                if hit_limit:
                    return

    dfs(0, [])
    if not solutions:
        raise RuntimeError("Current scene list cannot be partitioned into contiguous groups between 6 and 14 seconds.")

    append_log("success", f"DFS grouping search completed with {len(solutions)} valid solutions.")
    if hit_limit:
        append_log("warning", f"Reached solution cap: {MAX_GROUPING_SOLUTIONS}. Search stopped early.")

    return solutions, hit_limit


def choose_final_grouping_plan(all_grouping_plans: List[List[List[int]]], append_log) -> List[List[int]]:
    shuffled_plans = all_grouping_plans[:]
    random.shuffle(shuffled_plans)
    chosen_plan = random.choice(shuffled_plans)
    append_log("info", f"Selected final grouping plan: {chosen_plan}")
    return chosen_plan


def merge_grouped_scene_files(
        chosen_grouping_plan: List[List[int]],
        original_scenes: List[dict],
        merged_output_directory: Path,
        base_public_url: str,
        append_log,
) -> List[dict]:
    merged_output_directory.mkdir(parents=True, exist_ok=True)
    merged_segments: List[dict] = []
    data_root = merged_output_directory.parents[3]

    for group_index, scene_indices in enumerate(chosen_grouping_plan, start=1):
        selected_scenes = [original_scenes[idx - 1] for idx in scene_indices]
        concat_file_path = merged_output_directory / f"group_{group_index:03d}_concat.txt"
        merged_file_path = merged_output_directory / f"group_{group_index:03d}.mp4"

        with concat_file_path.open("w", encoding="utf-8") as concat_file:
            for scene in selected_scenes:
                safe_path = scene["file_path"].replace("'", "'\\''")
                concat_file.write(f"file '{safe_path}'\n")

        ffmpeg_command = [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_file_path),
            "-c",
            "copy",
            str(merged_file_path),
        ]
        command_result = subprocess.run(
            ffmpeg_command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if command_result.returncode != 0:
            stderr_text = command_result.stderr.decode("utf-8", errors="replace")
            raise RuntimeError(f"ffmpeg merge failed for group {group_index}: {stderr_text}")

        concat_file_path.unlink(missing_ok=True)

        start_seconds = selected_scenes[0]["start_seconds"]
        end_seconds = selected_scenes[-1]["end_seconds"]
        duration_seconds = end_seconds - start_seconds
        merged_segments.append(
            {
                "group_index": group_index,
                "start_seconds": start_seconds,
                "end_seconds": end_seconds,
                "duration_seconds": duration_seconds,
                "source_scene_index_range": [scene_indices[0], scene_indices[-1]],
                "source_scene_files": [scene["file_path"] for scene in selected_scenes],
                "export_file_path": str(merged_file_path),
                "export_public_url": build_media_url(base_public_url, data_root, merged_file_path),
            }
        )

    append_log("success", f"Merged grouped scenes into {len(merged_segments)} final segments.")
    return merged_segments


def process_single_video(
        source_video_path: Path,
        task_root_directory: Path,
        base_public_url: str,
        video_name: str,
        task_log_sink: List[dict],
        on_segments_ready=None,
        on_segment_analysis=None,
) -> VideoProcessResult:
    video_logs: List[dict] = []

    def append_video_log(level: str, message: str):
        entry = make_log(level, message, video_name)
        video_logs.append(entry)
        task_log_sink.append(entry)

    try:
        scene_directory = task_root_directory / "original_scenes" / source_video_path.stem
        merged_directory = task_root_directory / "merged_segments" / source_video_path.stem

        original_scenes = detect_and_split_original_scenes(
            source_video_path=source_video_path,
            scene_output_directory=scene_directory,
            base_public_url=base_public_url,
            video_name=video_name,
            append_log=append_video_log,
        )

        all_groupings, _ = search_valid_continuous_groupings(original_scenes, append_video_log)
        chosen_plan = choose_final_grouping_plan(all_groupings, append_video_log)
        merged_segments = merge_grouped_scene_files(
            chosen_grouping_plan=chosen_plan,
            original_scenes=original_scenes,
            merged_output_directory=merged_directory,
            base_public_url=base_public_url,
            append_log=append_video_log,
        )

        for segment in merged_segments:
            segment["analysis_status"] = "pending"
            segment["analysis"] = None
            segment["analysis_error_message"] = None

        if callable(on_segments_ready):
            on_segments_ready(merged_segments)

        analysis_status = "completed"
        can_run_analysis = bool(DASHSCOPE_API_KEY and VIDEO_ANALYSIS_MODEL_NAME and dashscope is not None)
        if not can_run_analysis:
            analysis_status = "skipped"
            append_video_log("warning", "未配置 DashScope 视频理解能力，已跳过片段提示词生成。")
            for segment in merged_segments:
                segment["analysis_status"] = "skipped"
                segment["analysis_error_message"] = "DashScope 未配置，已跳过生成。"
                if callable(on_segment_analysis):
                    on_segment_analysis(segment["group_index"] - 1, segment)
        else:
            for segment_index, segment in enumerate(merged_segments):
                try:
                    segment["analysis"] = analyze_segment_prompt(segment, append_video_log)
                    segment["analysis_status"] = "completed"
                except Exception as error:
                    analysis_status = "partial_failed"
                    segment["analysis_status"] = "failed"
                    segment["analysis_error_message"] = str(error)
                    append_video_log(
                        "error",
                        f"片段 group_{segment['group_index']:03d} 提示词生成失败: {error}",
                    )
                if callable(on_segment_analysis):
                    on_segment_analysis(segment_index, segment)

        summary = {
            "original_scene_count": len(original_scenes),
            "merged_segment_count": len(merged_segments),
            "total_original_duration_seconds": sum(scene["duration_seconds"] for scene in original_scenes),
            "total_merged_duration_seconds": sum(segment["duration_seconds"] for segment in merged_segments),
        }
        append_video_log("success", "Video processing completed successfully.")

        return VideoProcessResult(
            video_name=video_name,
            status="success",
            original_scenes=original_scenes,
            merged_segments=merged_segments,
            chosen_grouping_plan=chosen_plan,
            summary=summary,
            logs=video_logs,
            analysis_status=analysis_status,
        )

    except Exception as error:
        append_video_log("error", f"Video processing failed: {error}")
        return VideoProcessResult(
            video_name=video_name,
            status="failed",
            error_message=str(error),
            logs=video_logs,
            summary={"original_scene_count": 0, "merged_segment_count": 0},
        )


def save_uploaded_files(upload_files, upload_directory: Path) -> List[Path]:
    upload_directory.mkdir(parents=True, exist_ok=True)
    saved_paths: List[Path] = []
    for upload_file in upload_files:
        safe_name = Path(upload_file.filename).name
        if not safe_name:
            continue
        target_path = upload_directory / safe_name
        upload_file.save(target_path)
        saved_paths.append(target_path)
    return saved_paths


def cleanup_directory(directory_path: Path) -> None:
    if directory_path.exists():
        shutil.rmtree(directory_path)
