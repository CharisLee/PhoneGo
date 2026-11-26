"""The long-task pieces: checkpoint, workspace, plan, claim check.

These were written on the phone, under a task that was failing, so the edge
cases are the point of this file: an unconfigured directory, a file that is not
what it claims to be, a plan shorter than the list it is asked about.
"""
import os

from phoneagent import claims, plan, runs, workspace


# -- the checkpoint --------------------------------------------------------
def test_an_unconfigured_run_dir_writes_nothing(tmp_path, monkeypatch):
    """Empty must mean "off", not "a file in the working directory".

    The first version joined "" with the file name and wrote last-run.json into
    whatever directory the process happened to be in -- on a phone that is the
    app's private storage, and load() then reported a checkpoint nobody made.
    """
    monkeypatch.chdir(tmp_path)
    runs.save("", runs.checkpoint(task="t", status=runs.RUNNING))
    assert not os.path.exists(tmp_path / "last-run.json")
    assert runs.load("") == {}


def test_a_checkpoint_round_trips_and_closes(tmp_path):
    directory = str(tmp_path)
    runs.save(directory, runs.checkpoint(task="找一家粤菜", status=runs.RUNNING,
                                         rounds=7, findings=["蘩楼 4.8"]))
    data = runs.load(directory)
    assert runs.resumable(data)
    assert "找一家粤菜" in runs.summary(data)

    runs.save(directory, runs.checkpoint(task="找一家粤菜", status=runs.DONE,
                                         answer="蘩楼"))
    assert not runs.resumable(runs.load(directory))


def test_a_waiting_run_is_resumable(tmp_path):
    directory = str(tmp_path)
    runs.save(directory, runs.checkpoint(task="t", status=runs.WAITING,
                                         question="人机验证"))
    assert runs.resumable(runs.load(directory))


def test_an_unwritable_checkpoint_does_not_raise(tmp_path):
    blocker = tmp_path / "not-a-dir"
    blocker.write_text("x", encoding="utf-8")
    runs.save(str(blocker), runs.checkpoint(task="t", status=runs.RUNNING))
    assert runs.load(str(blocker)) == {}


# -- the workspace ---------------------------------------------------------
def test_notes_append_and_read_back(tmp_path):
    directory = str(tmp_path)
    assert workspace.append(directory, "餐厅", "蘩楼 4.8 人均92")
    assert workspace.append(directory, "地址", "嘉宾路4051号")
    text = workspace.read(directory)
    assert "蘩楼 4.8 人均92" in text and "嘉宾路4051号" in text
    assert workspace.tail(directory, 10) == text[-10:].strip()


def test_notes_rotate_instead_of_growing_forever(tmp_path, monkeypatch):
    """A phone has no one to clean up after a chatty model."""
    directory = str(tmp_path)
    monkeypatch.setattr(workspace, "MAX_BYTES", 200)
    for i in range(20):
        workspace.append(directory, f"n{i}", "x" * 40)
    assert os.path.exists(tmp_path / "notes.old.md")
    assert os.path.getsize(tmp_path / "notes.md") < 400


def test_a_missing_workspace_is_silent(tmp_path):
    assert workspace.append("", "t", "x") is False
    assert workspace.read("") == ""
    assert workspace.tail("") == ""
    workspace.save_result("", "t", "a")   # must not raise


# -- the plan --------------------------------------------------------------
def test_the_plan_skips_what_is_done():
    steps = [{"subtask": "找店", "app": "小红书"},
             {"subtask": "看评分", "app": "大众点评"}]
    import tempfile
    directory = tempfile.mkdtemp()
    saved = plan.save(directory, "跨 App 任务", steps)
    assert plan.summary(saved).startswith("计划 0/2")

    plan.mark(directory, 0, plan.DONE, "找到 蜀大侠")
    data = plan.load(directory)
    assert plan.resume_point(data) == 1
    assert plan.carry_of(data, upto=1) == "找到 蜀大侠"

    plan.mark(directory, 1, plan.DONE, "4.7")
    assert plan.resume_point(plan.load(directory)) == -1


def test_a_plan_that_is_not_one_is_ignored(tmp_path):
    (tmp_path / "plan.json").write_text("[1, 2, 3]", encoding="utf-8")
    assert plan.load(str(tmp_path)) == {}
    plan.mark(str(tmp_path), 0, plan.DONE, "x")     # no-op, no raise
    assert plan.resume_point({}) == -1
    assert plan.carry_of({}) == ""


# -- the answer check ------------------------------------------------------
def test_prices_ratings_and_names_are_checked():
    answer = ("找到「蘩楼(万象城金威大厦店)」，评分4.8，人均¥92，"
              "两人餐约¥209，打车约11元起。")
    notes = "蘩楼(万象城金威大厦店) 评分4.8 人均92元 打车11元起"
    checked, missing = claims.verify(answer, [notes])
    assert {c["raw"] for c in checked} >= {"¥92", "评分4.8"}
    assert "¥209" in missing


def test_a_duration_is_not_a_rating():
    """"45 小时 0 分" was read as the rating "0 分"."""
    claims_found = claims.extract("可用时长 45 小时 0 分")
    assert not [c for c in claims_found if c["kind"] == "rating"]


def test_prose_inside_quotes_is_not_a_name():
    claims_found = claims.extract("「0 分、省电与电池」")
    assert not [c for c in claims_found if c["kind"] == "name"]


def test_numbers_from_the_instruction_are_not_claims():
    task = "找一家适合两个人吃的粤菜，人均100左右，评分4.5以上"
    answer = "蘩楼，人均¥92（约100元），评分4.8"
    checked, missing = claims.verify(answer, ["蘩楼 人均92元 评分4.8"], given=task)
    assert missing == []


def test_no_sources_means_no_verdict():
    assert claims.verify("人均¥92", []) == ([], [])
