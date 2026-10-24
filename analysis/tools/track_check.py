"""Track 工程检查：规范读取、局部参数、时间追溯与任务隔离；不改写 raw。"""
from pathlib import Path
import sys
sys.dont_write_bytecode=True
PROJECT=next(p for p in Path(__file__).resolve().parents if (p/"global_settings.py").is_file())
sys.path[:0]=[str(PROJECT),str(PROJECT/"analysis"),str(PROJECT/"analysis/tools")]

from copy import deepcopy
from datetime import datetime
import tempfile
import pandas as pd

import global_settings as settings
from artifacts import write_json, read_json, sha256
from paths import ANALYSIS, processed_root, raw
from track_io import read_table, read_session, write_table, convert_types
from workflow import load_script, resolve_steps, script_path
from table_flow import run_flow
from run_records import run_id, script_history
from lab_history import collect
from data_lab.track.description.experiment import (
    EXPERIMENT_DIR, STAGES, STEP_ORDER, resolve_tasks, load_config,
)
ENTRY=EXPERIMENT_DIR/"track_describe.py"

def main():
    checks=[]
    base=EXPERIMENT_DIR/"results/_provenance/checks"   # 检查结果随最近一次结果存放，下次运行时一并清空
    base.mkdir(parents=True,exist_ok=True)
    module=load_script(ENTRY,"track_check_description")
    parameters=deepcopy(module.PARAMETERS)
    with tempfile.TemporaryDirectory(prefix="nbi_track_fixture_") as temporary:
        folder=Path(temporary)
        absent=read_table(folder,"tap")
        assert absent.attrs["present"] is False
        pd.DataFrame(columns=settings.table_columns("tap")).to_csv(folder/"tap.csv",index=False)
        empty=read_table(folder,"tap",formatted=True)
        assert empty.attrs["present"] and empty.empty
        checks.append("缺失文件与存在但零行的表保持区别")
        values={name:"0" if settings.TRACK_TYPES[field] in ("Float64","Int64") else ""
                for field,name in settings.TRACK_COLUMNS["tap"].items()}
        values[settings.column("tap","is_touched")]="FALSE"
        values[settings.column("tap","block_type")]="None"
        frame=pd.DataFrame([values],dtype="string")
        write_table(folder,"tap",frame)
        reread=read_table(folder,"tap")
        assert reread[settings.column("tap","block_type")].iloc[0]=="None"
        assert convert_types(reread,"tap")[settings.column("tap","is_touched")].iloc[0]==False
        checks.append("None 字面值保留，FALSE 不会被转换成真")
        original=settings.TRACK_COLUMNS["tap"]["cam_x"]
        try:
            settings.TRACK_COLUMNS["tap"]["cam_x"]="configured_camera_x"
            write_table(folder,"tap",frame.rename(columns={original:"configured_camera_x"}))
            assert "configured_camera_x" in read_table(folder,"tap",formatted=True)
        finally:
            settings.TRACK_COLUMNS["tap"]["cam_x"]=original
        checks.append("读取实际采用 global_settings 的集中列名")
        invalid=frame.copy()
        invalid[settings.column("tap","is_touched")]="invalid"
        try:
            convert_types(invalid,"tap")
        except ValueError:
            pass
        else:
            raise AssertionError("非法布尔值被接受")
        checks.append("非法布尔值明确报错")
    assert resolve_tasks(("track_describe","track_clean"))==list(STEP_ORDER)
    checks.append("组合任务正确补齐依赖且不重复执行")
    try:
        resolve_steps({"a":{"requires":("b",)},"b":{"requires":("a",)}},("a",),("a","b"))
    except ValueError:
        pass
    else:
        raise AssertionError("循环依赖被接受")
    checks.append("循环依赖拒绝执行")
    try:
        script_path(ANALYSIS,"data_lab/track/deprecated/discarded.py")
    except ValueError:
        pass
    else:
        raise AssertionError("废弃工具可进入调度")
    checks.append("废弃工具不能被执行")
    for name in ("track","psycho","physio","integration"):
        try:
            run_flow(name,{"dataset":"pilot"})
        except NotImplementedError:
            pass
        else:
            raise AssertionError("未实现的制表流程伪装为成功")
    checks.append("四个制表流程均明确标为预留")
    source_digest=sha256(ENTRY)
    configured=load_config(parameters,{"time_bin_seconds":30,"language":"en"})
    assert configured.description.time_bin_seconds==30 and configured.language=="en"
    assert parameters==module.PARAMETERS and sha256(ENTRY)==source_digest
    checks.append("CLI 覆盖与脚本参数共用加载器，原参数与源码不回写")
    for override in ({"tasks":["unknown"]},{"dataset":"unknown"},{"subject":"P*"},
                     {"time_bin_seconds":-1}):
        try:
            load_config(parameters,override)
        except ValueError:
            pass
        else:
            raise AssertionError("非法参数被接受")
    checks.append("非法选择及数值在输出前被拒绝")
    candidates=sorted(processed_root("test","track").glob("**/03_format/*/tables"),reverse=True)
    for candidate in candidates:
        tables=read_session(candidate,formatted=True)
        if tables["tap"].attrs["present"] and not tables["tap"].empty:
            a=module.describe(tables,candidate.parent.name,load_config(parameters,{"time_bin_seconds":60}).description)
            b=module.describe(tables,candidate.parent.name,load_config(parameters,{"time_bin_seconds":30}).description)
            assert len(b[3])>len(a[3])
            assert a[0]["tap"]==b[0]["tap"]
            assert int(a[3].tap_n.sum())==int(b[3].tap_n.sum())==len(tables["tap"])
            break
    else:
        raise AssertionError("缺少标准表，先执行记录描述实验")
    checks.append("分箱参数进入实际计算，改变分箱但保持事件总数")
    assert not any(hasattr(settings,key) for key in ("ROOT","RUN","TASKS","REPORTS_DIR","APP_PIPELINE"))
    assert set(settings.METRICS)==set(settings.DATA_OBJECTS)
    assert all(isinstance(value,dict) for value in settings.METRICS.values())
    checks.append("共享设置仅包含数据规范，指标登记按数据对象组织")
    assert not any((PROJECT/name).exists() for name in ("00_settings.py","01_parameters.py","02_run.py","reports"))
    checks.append("根目录旧设置、参数、运行器和 reports 已移除")
    events=collect(object_name="track")
    assert events and all(datetime.fromisoformat(row["at"]).tzinfo for row in events)
    assert any(row["action"]=="first_versioned" for row in events)
    for path in (ANALYSIS/"data_lab/track").rglob("*.py"):
        if not set(path.relative_to(ANALYSIS).parts)&{"archive","outputs","results","save","deprecated"}:
            assert script_history(path),path
    checks.append("活跃 Lab 脚本有带时区的历史登记，可按时间检索")
    manifest_path=EXPERIMENT_DIR/"results/_provenance/manifest.json"
    assert manifest_path.is_file(),"先运行一次记录描述以验证运行记录"
    completed=read_json(manifest_path)
    assert completed["status"]=="complete"
    start,end=map(datetime.fromisoformat,(completed["started_at"],completed["finished_at"]))
    assert start<=end
    previous=start
    for step in completed["steps"]:
        left,right=map(datetime.fromisoformat,(step["started_at"],step["finished_at"]))
        assert previous<=left<=right<=end and step["status"]=="complete"
        previous=right
    assert completed["git"]["available"]
    assert completed["raw_files_unchanged"] and completed["source_files_unchanged"]
    for path in completed.get("uncommitted_copied",[]):
        assert sha256(Path(completed["uncommitted_sources"])/path)==completed["script_sha256"][path]
    checks.append("运行与各步骤时间有序，Git 提交号与未提交源码副本校验完整")
    path=base/("track_check_"+run_id()+".json")
    write_json(path,{"passed":True,"checks":checks,"raw_data_written":False})
    print(path)
    print("PASS:",len(checks),"checks")
    return checks

if __name__=="__main__":
    main()
