from pathlib import Path
import os,subprocess,sys
ROOT=Path(__file__).resolve().parents[1]
env=os.environ.copy();env['PYTHONPATH']=str(ROOT/'src')
sys.exit(subprocess.call([sys.executable,'-m','unittest','discover','-s','tests','-v'],cwd=ROOT,env=env))
