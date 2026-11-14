# ollama-vulkan

本 fork 只负责构建 **仅含 CPU + Vulkan 后端** 的 ollama Docker 镜像，推送到
`ghcr.io/<owner>/ollama-vulkan`。

## 工作方式

构建时直接 checkout **上游 `ollama/ollama`** 的源码（不是本仓库的代码），再用
`patch_dockerfile.py` 改写上游 Dockerfile：

- `base-amd64`：把几十 GB 的 `rocm/dev-almalinux-8` 换成 `almalinux:8` + gcc-toolset-13
- `amd64` 组装阶段：只保留 `llama-server-cpu` 和 `llama-server-vulkan`，
  CUDA / ROCm / MLX 阶段不再被引用，BuildKit 不会构建它们
- 版本号通过 `GOFLAGS` build-arg 注入（与上游 release 流程一致）

上游 Dockerfile 结构再变时，脚本会直接报错退出，而不是生成一个坏掉的构建。

## Workflows

| 文件 | 触发 | 作用 |
| --- | --- | --- |
| `Auto build Vulkan docker image.yaml` | 每天 02:00 UTC / 手动 | 上游有新 release 且 GHCR 中没有该 tag 时构建，推送 `:<tag>` 和 `:latest` |
| `build-vulkan.yml` | 手动 | 构建任意上游 ref（默认 `main`），只推送 `:<ref>` |
| `vulkan-image.yml` | 被上面两个调用 | 实际的构建 / 推送 / 校验 |

## 同步上游代码

镜像构建不依赖本仓库的代码，同步只是为了让仓库保持最新：

```bash
git remote add upstream https://github.com/ollama/ollama   # 仅首次
git fetch upstream
git merge upstream/main
# 若上游新增/修改了 .github/workflows 下的 CI，删掉即可（本 fork 不需要）
```

## 注意

- GitHub 会在仓库 60 天无提交后自动停用定时 workflow；自动构建里的 `keepalive` job 每次运行都会通过 API 重新启用自己。如果已经被停用，需要到 Actions 页面手动 Enable 一次。
- 上游 Dockerfile 结构变化时构建会直接失败，GitHub 会发邮件通知；届时需要更新 `patch_dockerfile.py`。
- 上游官方镜像 `ollama/ollama` 现已内置 Vulkan 且默认启用；本镜像的优势是体积小（不含 CUDA/ROCm）。
