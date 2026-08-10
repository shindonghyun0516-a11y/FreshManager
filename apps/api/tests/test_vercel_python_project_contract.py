from collections import Counter
from pathlib import Path
import tomllib
import unittest


class VercelPythonProjectContractTests(unittest.TestCase):
    def test_vercel_python_project_contract(self) -> None:
        repository_root = Path(__file__).resolve().parents[3]
        with (repository_root / "pyproject.toml").open("rb") as file:
            configuration = tomllib.load(file)

        self.assertIn("project", configuration)
        project = configuration["project"]
        self.assertEqual(project["name"], "freshmanager-api")
        self.assertEqual(project["version"], "0.1.0")
        self.assertEqual(project["requires-python"], ">=3.12,<3.13")
        self.assertEqual(len(project["dependencies"]), 3)

        requirements = [
            line.strip()
            for line in (repository_root / "requirements.txt").read_text().splitlines()
            if line.strip()
        ]
        self.assertEqual(Counter(project["dependencies"]), Counter(requirements))
        self.assertEqual(configuration["tool"]["vercel"]["entrypoint"], "apps.api.main:app")
        self.assertNotIn("build-system", configuration)
        self.assertNotIn("scripts", project)


if __name__ == "__main__":
    unittest.main()
