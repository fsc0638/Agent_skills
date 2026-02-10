import os
import yaml
import json
import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger("ManifestGenerator")

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILLS_DIR = os.path.join(PROJECT_ROOT, "skills")
MANIFEST_PATH = os.path.join(PROJECT_ROOT, "skills_manifest.json")

def generate_manifest():
    manifest = {
        "version": "1.0.0",
        "skills": []
    }

    if not os.path.exists(SKILLS_DIR):
        logger.error(f"Skills directory not found: {SKILLS_DIR}")
        return

    for skill_name in os.listdir(SKILLS_DIR):
        skill_path = os.path.join(SKILLS_DIR, skill_name)
        if not os.path.isdir(skill_path):
            continue

        skill_md_path = os.path.join(skill_path, "SKILL.md")
        if not os.path.exists(skill_md_path):
            logger.warning(f"SKILL.md missing for {skill_name}")
            continue

        try:
            with open(skill_md_path, 'r', encoding='utf-8') as f:
                content = f.read()
                # Extract YAML frontmatter
                if content.startswith('---'):
                    parts = content.split('---', 2)
                    if len(parts) >= 3:
                        metadata = yaml.safe_load(parts[1])
                        
                        # Extract and refine data
                        manifest["skills"].append({
                            "id": skill_name,
                            "name": metadata.get("name", skill_name),
                            "version": metadata.get("version", "1.0.0"),
                            "description": metadata.get("description", "").strip(),
                            "runtime_requirements": metadata.get("runtime_requirements", []),
                            "estimated_tokens": metadata.get("estimated_tokens", 500),
                            "requires_venv": metadata.get("requires_venv", False),
                            "parameters": metadata.get("parameters", {})
                        })
                        logger.info(f"Indexed skill: {skill_name}")
        except Exception as e:
            logger.error(f"Failed to index {skill_name}: {e}")

    with open(MANIFEST_PATH, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    
    logger.info(f"Manifest generated at: {MANIFEST_PATH}")

if __name__ == "__main__":
    generate_manifest()
