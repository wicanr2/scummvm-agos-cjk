# 授權

## 引擎 patch

`patches/agos-cjk.patch` 是對 [ScummVM](https://www.scummvm.org/) 的修改,
衍生自 ScummVM 原始碼,依 **GPLv3** 釋出。散布修改過的 binary 時請一併提供
對應原始碼與修改說明。基準版本記於 [`patches/UPSTREAM.md`](patches/UPSTREAM.md)。

## 工具

`tools/` 下的腳本同樣以 GPLv3 釋出。

## 字型

`tools/build_eten_font.py` 是**格式轉換工具**,不含任何字型資料。
倚天中文系統(ETEN 3.53)的點陣字模有版權,**不隨本 repo 散布**,需自備。
`build_cjk_font.py` 可從開源字型(如 Noto Sans CJK, SIL OFL 1.1)烘出可散布的替代版本。

## 遊戲原檔

本 repo 不含任何遊戲資料。使用者需自備合法擁有的遊戲檔案。
