# 数据

命名规范与调取方法见项目根目录 README.md"数据命名规范"一节：每份数据由 dataset（formal / pilot / test）、layer（raw / processed / final，另有 supplementary）、pipeline（track / psycho / physio）、subject（如 P040）定位，调取一律通过 analysis/tools/data_access.py。

- formal/ 只放正式实验数据；pilot_and_test/ 下放预实验（pilot/）与开发测试（test/），三者绝对隔离。
- raw/ 只读，原样拷入；processed/、final/ 由脚本生成，可删可重建。
- 本目录下的数据不入库，只存本机，另用移动硬盘备份。
