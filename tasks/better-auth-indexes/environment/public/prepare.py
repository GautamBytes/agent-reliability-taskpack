from pathlib import Path
import shutil
root=Path('/app/repo')
(root/'_task_public').mkdir(exist_ok=True)
shutil.copyfile('/opt/task-public/preservation-migrations.test.ts',root/'_task_public/preservation-migrations.test.ts')
shutil.copyfile('/opt/task-public/vitest.config.ts',root/'vitest.task.config.ts')
