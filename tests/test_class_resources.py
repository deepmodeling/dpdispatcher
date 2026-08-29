import json
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
__package__ = "tests"
# from .context import LocalSession
# from .context import LocalContext
from .context import (
    Resources,
    setUpModule,  # noqa: F401
)
from .sample_class import SampleClass


class TestResources(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None
        self.resources = SampleClass.get_sample_resources()
        self.resources_dict = SampleClass.get_sample_resources_dict()

    def test_eq(self):
        self.assertEqual(self.resources, SampleClass.get_sample_resources())

    def test_serialize(self):
        self.assertEqual(self.resources.serialize(), self.resources_dict)

    def test_deserialize(self):
        resources = Resources.deserialize(resources_dict=self.resources_dict)
        self.assertEqual(self.resources, resources)

    def test_serialize_deserialize(self):
        self.assertEqual(
            self.resources,
            Resources.deserialize(resources_dict=self.resources.serialize()),
        )

    def test_resources_json(self):
        with open("jsons/resources.json") as f:
            resources_json_dict = json.load(f)
        self.assertTrue(resources_json_dict, self.resources_dict)
        self.assertTrue(resources_json_dict, self.resources.serialize())

    def test_arginfo(self):
        self.resources.arginfo()

    def test_load_from_json(self):
        resources = Resources.load_from_json("jsons/resources.json")
        self.assertTrue(resources, self.resources)

    def test_default_collections_are_independent(self):
        first = Resources(1, 1, 0, "", 1)
        second = Resources(1, 1, 0, "", 1)

        collection_attributes = (
            "custom_flags",
            "strategy",
            "module_unload_list",
            "module_list",
            "source_list",
            "envs",
            "prepend_script",
            "append_script",
            "kwargs",
        )
        for attribute in collection_attributes:
            with self.subTest(attribute=attribute):
                self.assertIsNot(getattr(first, attribute), getattr(second, attribute))

        first.custom_flags.append("# custom")
        first.strategy["ratio_unfinished"] = 0.5
        first.envs["NAME"] = "value"
        self.assertEqual(second.custom_flags, [])
        self.assertEqual(second.strategy["ratio_unfinished"], 0.0)
        self.assertEqual(second.envs, {})

    def test_input_collections_are_copied(self):
        custom_flags = ["# custom"]
        strategy = {"ratio_unfinished": 0.25}
        module_list = ["python"]
        envs = {"PATHS": ["one"]}
        prepend_script = ["echo before"]
        backend_kwargs = {"nested": {"value": 1}}

        resources = Resources(
            1,
            1,
            0,
            "",
            1,
            custom_flags=custom_flags,
            strategy=strategy,
            module_list=module_list,
            envs=envs,
            prepend_script=prepend_script,
            kwargs=backend_kwargs,
        )

        self.assertEqual(strategy, {"ratio_unfinished": 0.25})

        custom_flags.append("# later")
        strategy["ratio_unfinished"] = 0.75
        module_list.append("cuda")
        envs["PATHS"].append("two")
        prepend_script.append("echo later")
        backend_kwargs["nested"]["value"] = 2

        self.assertEqual(resources.custom_flags, ["# custom"])
        self.assertEqual(resources.strategy["ratio_unfinished"], 0.25)
        self.assertEqual(resources.strategy["if_cuda_multi_devices"], False)
        self.assertEqual(resources.module_list, ["python"])
        self.assertEqual(resources.envs, {"PATHS": ["one"]})
        self.assertEqual(resources.prepend_script, ["echo before"])
        self.assertEqual(resources.kwargs, {"nested": {"value": 1}})

        resources.custom_flags.append("# internal")
        resources.envs["PATHS"].append("internal")
        self.assertEqual(custom_flags, ["# custom", "# later"])
        self.assertEqual(envs, {"PATHS": ["one", "two"]})
