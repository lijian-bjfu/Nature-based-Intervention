"""APP 工程检查：类型、历史值、空表/缺文件和集中列名配置；不写入 data。"""
from pathlib import Path
import sys
sys.dont_write_bytecode = True
ROOT = next(p for p in Path(__file__).resolve().parents if (p/"settings.py").is_file())
sys.path.insert(0,str(ROOT))
import settings
sys.path.insert(0,str(settings.TOOLS_DIR))
from datetime import datetime
import tempfile
import pandas as pd
from app_io import read_table, convert_types, write_table
from artifacts import write_json
from paths import report_root, processed_root, final_root, stage_dir
from pipeline import resolve_steps

def main():
    checks=[]
    base=report_root("pilot_and_test", "app")/"checks"
    base.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=base,prefix="app_check_") as temp:
        folder=Path(temp)
        missing=read_table(folder,"tap")
        assert not missing.attrs["present"]
        pd.DataFrame(columns=settings.table_columns("tap")).to_csv(folder/settings.APP_FILES["tap"],index=False)
        empty=read_table(folder,"tap",formatted=True)
        assert empty.attrs["present"] and empty.empty
        checks.append("Missing file differs from present empty table")
        values={name:"0" if settings.APP_TYPES[field] in ("Float64","Int64") else ""
                for field,name in settings.APP_COLUMNS["tap"].items()}
        values[settings.column("tap","is_touched")]=settings.APP_FALSE
        values[settings.column("tap","block_type")]="None"
        frame=pd.DataFrame([values],dtype="string")
        write_table(folder,"tap",frame)
        reread=read_table(folder,"tap")
        assert reread[settings.column("tap","block_type")].iloc[0]=="None"
        assert reread[settings.column("tap","is_touched")].iloc[0]==settings.APP_FALSE
        converted=convert_types(reread,"tap")
        assert converted[settings.column("tap","is_touched")].iloc[0]==False
        checks.append("Literal None preserved; FALSE stays false through string and typed writes")
        old=settings.APP_COLUMNS["tap"]["cam_x"]
        changed="configured_camera_x"
        try:
            settings.APP_COLUMNS["tap"]["cam_x"]=changed
            renamed=frame.rename(columns={old:changed})
            write_table(folder,"tap",renamed)
            parsed=read_table(folder,"tap",formatted=True)
            assert changed in parsed and old not in parsed
        finally:
            settings.APP_COLUMNS["tap"]["cam_x"]=old
        checks.append("External column rename requires settings change only")
        invalid=frame.copy()
        invalid[settings.column("tap","is_touched")]="not_a_boolean"
        try:
            convert_types(invalid,"tap")
        except ValueError:
            checks.append("Invalid boolean fails explicitly")
        else:
            raise AssertionError("Invalid boolean was silently accepted")
        assert resolve_steps(("06_analysis",))==["01_import","02_clean","03_format","06_analysis"]
        checks.append("Selecting 06 resolves ordered prerequisites")
        try:
            resolve_steps(("04_features",))
        except ValueError:
            checks.append("Unimplemented metric stage fails explicitly")
        else:
            raise AssertionError("Unimplemented stage appeared to run")
        assert report_root("formal")!=report_root("pilot_and_test")
        assert report_root(settings.DATASETS["pilot"]["report_group"]) == report_root(settings.DATASETS["logging_test"]["report_group"])
        assert report_root("pilot_and_test") == settings.REPORTS_DIR/"pilot_and_test"/"app"
        checks.append("Reports separated by formal/test and work topic, not dataset")
        context = {"output": report_root("pilot_and_test")/"runs"/"check",
                   "processed_output": processed_root("logging_test","app")/"check",
                   "final_output": final_root("logging_test")/"check"}
        assert stage_dir(context,"02_clean").is_relative_to(settings.DATA_DIR)
        assert stage_dir(context,"03_format").is_relative_to(settings.DATA_DIR)
        assert stage_dir(context,"05_integrate").is_relative_to(final_root("logging_test"))
        assert stage_dir(context,"06_analysis").is_relative_to(settings.REPORTS_DIR)
        assert not stage_dir(context,"02_clean").is_relative_to(settings.REPORTS_DIR)
        checks.append("Processing and final tables route to data; analysis results route to reports")
    path=base/("app_check_"+datetime.now().strftime("%Y%m%d_%H%M%S_%f")+".json")
    write_json(path,{"passed":True,"checks":checks,"raw_data_written":False})
    print(path)
    print("PASS:",len(checks),"checks")

if __name__=="__main__":
    main()
