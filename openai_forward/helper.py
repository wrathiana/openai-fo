import ast
import inspect
import os
from pathlib import Path
from typing import Dict, List, Union

import orjson
from fastapi import Request
from rich import print


def get_client_ip(request: Request):
    if "x-forwarded-for" in request.headers:
        return request.headers["x-forwarded-for"].split(",")[0]
    elif not request.client or not request.client.host:
        return "127.0.0.1"
    return request.client.host


def relp(rel_path: Union[str, Path], parents=0, return_str=True, strict=False):
    currentframe = inspect.currentframe()
    f = currentframe.f_back
    for _ in range(parents):
        f = f.f_back
    current_path = Path(f.f_code.co_filename).parent
    pathlib_path = current_path / rel_path
    pathlib_path = pathlib_path.resolve(strict=strict)
    if return_str:
        return str(pathlib_path)
    else:
        return pathlib_path


def ls(_dir, *patterns, concat='extend', recursive=False):
    from glob import glob

    path_list = []
    for pattern in patterns:
        if concat == 'extend':
            path_list.extend(glob(os.path.join(_dir, pattern), recursive=recursive))
        else:
            path_list.append(glob(os.path.join(_dir, pattern), recursive=recursive))
    return path_list


def json_load(filepath: str, rel=False, mode="rb"):
    abs_path = relp(filepath, parents=1) if rel else filepath
    with open(abs_path, mode=mode) as f:
        return orjson.loads(f.read())


def json_dump(
    data: Union[List, Dict], filepath: str, rel=False, indent_2=False, mode="wb"
):
    orjson_option = 0
    if indent_2:
        orjson_option = orjson.OPT_INDENT_2
    abs_path = relp(filepath, parents=1) if rel else filepath
    with open(abs_path, mode=mode) as f:
        f.write(orjson.dumps(data, option=orjson_option))


def toml_load(filepath: str, rel=False):
    import toml

    abs_path = relp(filepath, parents=1) if rel else filepath
    return toml.load(abs_path)


def str2list(s: str, sep):
    if s:
        return [i.strip() for i in s.split(sep) if i.strip()]
    else:
        return []


def env2list(env_name: str, sep=","):
    return str2list(os.environ.get(env_name, "").strip(), sep=sep)


def env2dict(env_name: str) -> Dict:
    import json

    env_str = os.environ.get(env_name, "").strip()
    if not env_str:
        return {}
    return json.loads(env_str)


def format_route_prefix(route_prefix: str):
    if route_prefix:
        if route_prefix.endswith("/"):
            route_prefix = route_prefix[:-1]
        if not route_prefix.startswith("/"):
            route_prefix = "/" + route_prefix
    return route_prefix


def get_matches(messages: List[Dict], assistants: List[Dict]):
    msg_len, ass_len = len(messages), len(assistants)
    if msg_len != ass_len:
        print(f"Length mismatch between message({msg_len}) and assistant({ass_len}) ")

    cvt = lambda msg, ass: {
        "datetime": msg.get('datetime'),
        "ip": msg.get("ip") or msg.get('forwarded-for'),
        "model": msg.get("model"),
        "messages": msg.get("messages"),
        "assistant": ass.get("assistant"),
    }

    msg_uid_dict = {m.pop("uid"): m for m in messages}
    ass_uid_dict = {a.pop("uid"): a for a in assistants}
    matches = [
        cvt(msg_uid_dict[uid], ass_uid_dict[uid])
        for uid in msg_uid_dict
        if uid in ass_uid_dict
    ]

    ref_len = max(msg_len, ass_len)
    if len(matches) != ref_len:
        print(f"There are {ref_len - len(matches)} mismatched items")
    return matches


def parse_log_to_list(log_path: str):
    with open(log_path, "r", encoding="utf-8") as f:
        messages, assistant = [], []
        for line in f.readlines():
            content: dict = ast.literal_eval(line)
            if content.get("messages"):
                messages.append(content)
            else:
                assistant.append(content)
    return messages, assistant


def convert_chatlog_to_jsonl(log_path: str, target_path: str):
    """Convert single chatlog to jsonl"""
    message_list, assistant_list = parse_log_to_list(log_path)
    content_list = get_matches(messages=message_list, assistants=assistant_list)
    json_dump(content_list, target_path, indent_2=True)


def get_log_files_from_folder(log_path: str):
    return ls(log_path, "*.log")


def convert_folder_to_jsonl(folder_path: str, target_path: str):
    """Convert chatlog folder to jsonl"""
    log_files = get_log_files_from_folder(folder_path)
    messages = []
    assistants = []
    for log_path in log_files:
        msg, ass = parse_log_to_list(log_path)

        msg_len, ass_len = len(msg), len(ass)
        if msg_len != ass_len:
            print(
                f"{log_path}: Length mismatch between message({msg_len}) and assistant({ass_len}) "
            )
        messages.extend(msg)
        assistants.extend(ass)
    content_list = get_matches(messages=messages, assistants=assistants)
    json_dump(content_list, target_path, indent_2=True)
    print("Converted successfully")
    print(f"File saved to {target_path}")
