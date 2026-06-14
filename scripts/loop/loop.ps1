# Lumen 自主开发循环（Loop Engineering / Ralph 有界半自主版）
# 用法: .\scripts\loop\loop.ps1 -MaxIterations 5
#
# 设计取舍（见调研报告）：对成熟代码库不裸跑 Ralph，而是"有界半自主"——
#   小迭代上限 + 分支隔离 + 测试当门禁 + 强制人工 review。
#
# 安全说明：本骨架**默认不加** --dangerously-skip-permissions，所以会按权限提示逐步确认，
#   适合首次 attended（人盯屏）试跑。无人值守过夜前，请务必先放进沙箱/容器再考虑加该标志。

param([int]$MaxIterations = 5)

$ErrorActionPreference = "Stop"
$repo   = "E:\ai\llmwiki"
$prompt = Join-Path $repo "scripts\loop\PROMPT_build.md"
$log    = Join-Path $repo "scripts\loop\loop.log"

# 护栏②：分支隔离 —— 绝不在 master/main 上直接跑
$branch = (git -C $repo rev-parse --abbrev-ref HEAD).Trim()
if ($branch -eq "master" -or $branch -eq "main") {
    $new = "auto/loop-" + (Get-Date -Format "yyyyMMdd-HHmm")
    git -C $repo switch -c $new
    Write-Host "已从 $branch 切到隔离分支 $new" -ForegroundColor Cyan
}

for ($i = 1; $i -le $MaxIterations; $i++) {   # 护栏④：循环上限，永不无限
    Write-Host "===== 第 $i / $MaxIterations 轮 =====" -ForegroundColor Yellow

    # 每轮全新上下文：headless 模式从 stdin 读 PROMPT；记忆全靠磁盘文件 + git 历史
    $promptText = Get-Content $prompt -Raw
    $out = $promptText | claude -p
    $out | Tee-Object -FilePath $log -Append | Out-Null

    # 护栏⑤：双信号收敛 / 阻塞即停
    if ($out -match "<promise>LUMEN_TASK_DONE</promise>") {
        Write-Host "可自主推进区全部完成，退出。" -ForegroundColor Green; break
    }
    if ($out -match "<promise>NEEDS_BOSS</promise>") {
        Write-Host "命中『需老板拍板』项，停止等决策。" -ForegroundColor Magenta; break
    }

    Start-Sleep -Seconds 5   # 护栏⑥：迭代间隔，缓解 API 限流
}

Write-Host "循环结束。请人工 review 分支 diff 再决定是否合并（护栏③：强制人工 review）：" -ForegroundColor Cyan
Write-Host "  git -C $repo diff master...HEAD" -ForegroundColor DarkGray
