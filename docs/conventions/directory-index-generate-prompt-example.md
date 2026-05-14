# Directory Index Prompt Example

The text below is an example of a prompt that might be fed to an agent working in a project that is installing Optimus for the first time.  The goal of the prompt is to generate the new `DIRECTORY_INDEX.md` doc that lists the project's most important directories and files (**not all** dirs and files)) and specs a known agent-friendly format.

e.g.: Use this as a guide for a prompt used to dispatch a sub-agent during Optimus install / setup, or convert it to an agent definition (per the IDE subagents feature) that can be used at any point during or after Optimus install.  These are just a couple ideas, so let's consider the options and determine where this information would be useful for the prod installed Optimus use cases.

---

Create a `DIRECTORY_INDEX.md` file at the root of this project.

Goal: build an agent-friendly directory index that helps future agents quickly decide where to look for a given work item.

Requirements:

1. List every non-hidden top-level directory.
2. Under each top-level directory, list the important source-code, code-holding, config, build/deploy, and main documentation directories one or two levels deep.
3. If a repo/project does not have a conventional `src/`, `source/`, or app directory, inspect it and identify where the real code or code-like assets live, such as:
   - `build/`
   - `scripts/`
   - `tools/`
   - `cmd/`
   - `lib/`
   - Docker/Packer/CloudFormation/Terraform directories
   - root-level app files like `index.js`, `Program.cs`, `main.py`, `Cargo.toml`, `package.json`, etc.
4. For each top-level project, include key files as nested bullets:
   - main README/docs
   - architecture or agent/workflow docs
   - app/service entrypoints
   - build manifests
   - local development files
   - deployment/config files
   - top/parent code files that help orient a new agent
5. Every listed directory and file needs a short one-line description.
6. Every bullet must start with one of these tags:
   - `[DIR]` directory
   - `[DOC]` documentation
   - `[ENTRY]` executable, app, service, or major workflow entrypoint
   - `[BUILD]` build/deploy manifest, Dockerfile, compose file, CI-related script, or package/build manifest
   - `[CONFIG]` configuration directory or file
   - `[FILE]` other important file
7. Keep every path fully qualified from the workspace root or at least from the submodule/project root so every single line is independently actionable.
   - Good: `[DIR] ms-core-api/src/main/ - Production Kotlin service code.`
   - Bad: `[DIR] src/main/ - Production code.`
8. Use concise descriptions. Do not dump every file. Focus on files and directories that help future agents route work quickly.
9. Do not include hidden directories such as `.git`, `.github`, `.cursor`, `node_modules`, `target`, `dist`, `build` output folders, caches, or generated binaries unless the directory itself is the source of infrastructure-as-code or scripts.
10. Preserve existing project changes. Do not delete or rewrite unrelated files.

Suggested output shape:

```markdown
# Directory Index

Workspace-level index for non-hidden top-level directories. Hidden directories such as `.git`, `.github`, and tool caches are intentionally omitted. Entries focus on source-code, code-holding infrastructure directories, main documentation directories, config/build assets, and key parent files.

Legend: `[DIR]` directory, `[DOC]` documentation, `[ENTRY]` executable or service entrypoint, `[BUILD]` build/deploy manifest or script, `[CONFIG]` configuration, `[FILE]` other key file.

## Top-Level Projects

- [DIR] `project-a/` - Brief project description.
  - [DIR] `project-a/src/` - Main application source code.
    - [DIR] `project-a/src/main/` - Production source tree.
    - [DIR] `project-a/src/test/` - Test source tree.
  - [CONFIG] `project-a/config/` - Runtime configuration files.
  - [DOC] `project-a/README.md` - Main setup and usage guide.
  - [ENTRY] `project-a/src/main/App.kt` - Service bootstrap entrypoint.
  - [BUILD] `project-a/pom.xml` - Maven build file.

- [DIR] `infra-project/` - Infrastructure automation project.
  - [BUILD] `infra-project/build/packer/` - Packer templates and AMI setup scripts.
  - [BUILD] `infra-project/build/cloudformation/` - CloudFormation deployment stacks.
  - [CONFIG] `infra-project/properties/` - Environment-specific install response files.
  - [DOC] `infra-project/README.md` - Infrastructure overview and usage guide.
  - [BUILD] `infra-project/build/packer/server/build.pkr.hcl` - Server AMI Packer template.
```

Verification before finishing:

1. Confirm every non-hidden top-level directory is represented.
2. Confirm all referenced paths exist.
3. Confirm there are no untagged bullets.
4. Confirm there are no vague “no source dir” notes where a code-holding directory or root-level code file exists.
5. Run available markdown/linter checks if the environment provides them.
