# runs 目录整理脚本说明

## 作用

`restructure_runs_layout.py` 用来把当前目录中的运行数据统一整理为下面的结构：

```text
场景/日期/sessionid/文件
```

它会同时处理两类来源：

1. `exports/YYYY-MM-DD/场景/sessionid`
2. 旧结构 `场景/sessionid`

整理完成后，目标结构示例：

```text
初中代数方程分步求解辅导/
  2026-03-18/
    7405110c-868d-46c9-be73-560574fce1eb/
      run.json
      teacher-messages.json
      conversation-messages.json
```

## 整理规则

### 1. 处理 `exports`

脚本会把：

```text
exports/日期/场景/sessionid/文件
```

移动到：

```text
场景/日期/sessionid/文件
```

### 2. 处理旧根目录结构

如果根目录下已经存在：

```text
场景/sessionid/文件
```

脚本会读取该 session 下的 `run.json`，优先使用：

1. `startedAt`
2. `finishedAt`

来推导日期，然后移动到：

```text
场景/日期/sessionid/文件
```

日期按 UTC 解析，输出格式为 `YYYY-MM-DD`。

## 冲突处理

脚本不会粗暴覆盖已有文件。

如果目标目录不存在：

1. 整个目录直接移动过去

如果目标目录已存在：

1. 同名文件内容完全一致：视为重复文件，源文件删除
2. 同名文件内容不同：记为冲突，不覆盖目标文件，保留源文件
3. 迁移后源目录为空：自动清理空目录

如果出现冲突，脚本最终会返回退出码 `1`。

## 使用方法

当前目录就是脚本所在目录时，推荐这样执行：

### 1. 先看预演结果

```bash
python3 -B restructure_runs_layout.py --summary-only
```

这一步不会改任何文件，只会输出汇总结果，例如：

```text
SUMMARY planned_moves=715 executed_moves=0 duplicate_files=0 conflicts=0 skipped_legacy=0 removed_empty_dirs=0
```

### 2. 查看详细预演日志

```bash
python3 -B restructure_runs_layout.py
```

会打印每一条计划中的移动、冲突、跳过和空目录清理信息。

### 3. 真正执行整理

```bash
python3 -B restructure_runs_layout.py --apply --summary-only
```

如果你希望看到每一条执行记录，可以去掉 `--summary-only`：

```bash
python3 -B restructure_runs_layout.py --apply
```

## 常用参数

### `--apply`

真正执行移动操作。

不加时为 dry-run，只预演不改文件。

### `--summary-only`

只输出最终汇总，不输出每一条日志。

### `--skip-legacy`

只整理 `exports`，不处理旧结构 `场景/sessionid`。

```bash
python3 -B restructure_runs_layout.py --summary-only --skip-legacy
```

### `--root`

指定要整理的根目录，默认是当前目录。

```bash
python3 -B restructure_runs_layout.py --root /path/to/runs --summary-only
```

### `--exports-dir`

指定 `exports` 目录位置，默认是 `./exports`。

```bash
python3 -B restructure_runs_layout.py --root /path/to/runs --exports-dir /path/to/runs/exports --summary-only
```

## 建议执行顺序

推荐按下面顺序执行：

1. 先跑 `dry-run --summary-only`，确认计划数量和冲突数
2. 如果需要，再跑详细 `dry-run` 查看具体会移动哪些目录
3. 确认无误后执行 `--apply`

推荐命令：

```bash
python3 -B restructure_runs_layout.py --summary-only
python3 -B restructure_runs_layout.py --apply --summary-only
```

## 输出字段说明

脚本最后会输出一行 `SUMMARY`，字段含义如下：

- `planned_moves`: 计划移动的目录或文件数量
- `executed_moves`: 实际完成的移动数量
- `duplicate_files`: 目标中已存在且内容相同的重复文件数量
- `conflicts`: 目标中已存在但内容不同的冲突数量
- `skipped_legacy`: 旧结构中因缺少 `run.json` 或无法推导日期而跳过的目录数量
- `removed_empty_dirs`: 执行过程中清理掉的空目录数量

## 文件位置

- 脚本：[restructure_runs_layout.py](/home/wsy/Projects/wsy/message_data/runs/restructure_runs_layout.py)
- 说明文档：[README.md](/home/wsy/Projects/wsy/message_data/runs/README.md)
