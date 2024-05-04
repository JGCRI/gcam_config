# import os
# import os.path as path
# import pkg_resources
# import tempfile
# import re
import lxml.etree as ET
from itertools import product
from xxhash import xxh32
import os
from scalable.caching import *
from copy import deepcopy

def hash_to_bytes(hash):
    return hash.to_bytes((hash.bit_length() + 7) // 8, 'big')

def generate_batch_permutations(base_config, batch_file):
    if isinstance(base_config, str):
        base_config = GcamConfig(base_config)
    base_config.set_batch_mode(0)
    base_config.set_target_finder_mode(0)
    parser = ET.XMLParser(strip_cdata=False)
    batch = ET.parse(batch_file, parser)
    comp_sets = list()
    for cs in batch.getroot().iterfind("./ComponentSet"):
        comp_sets.append(cs.findall("./FileSet"))
    runner_sets = batch.getroot().findall("./runner-set/*")
    if len(runner_sets) > 0:
        comp_sets.append(runner_sets)
    prod_out = product(*comp_sets)
    configs_out = list()
    for permutation in prod_out:
        scenario_name = list()
        curr_config = deepcopy(base_config)
        for file_set in permutation:
            name = ""
            if file_set.tag == "FileSet":
                name = file_set.get("name")
                curr_config.add_scenario_components(file_set)
            elif file_set.tag == "Value":
                name = file_set.get("name")
                curr_config.set_target_finder_mode(1, file_set.text)
            elif file_set.tag == "single-scenario-runner":
                name = ""
            scenario_name.append(name)
        scenario_name = "".join(scenario_name)
        curr_config.set_scenario_name(scenario_name)
        configs_out.append(curr_config)
    return configs_out

class GcamConfig:
    def __init__(self, config_in):
        parser = ET.XMLParser(strip_cdata=False)
        self.config_file = config_in
        self.config_dir = os.path.join(os.path.abspath(os.path.dirname(self.config_file)))
        self.config_doc = ET.parse(config_in, parser)
    
    def __hash__(self):
        digest = 0
        x = xxh32(seed=SEED)
        x.update(hash_to_bytes(hash(FileType(self.config_file))))
        root = self.config_doc.getroot()
        scn_components = root.find("./ScenarioComponents")
        for component in scn_components:
            if not isinstance(component, ET._Comment):
                if component.text:
                    component_path = os.path.join(self.config_dir, component.text)
                    if os.path.exists(component_path):
                        if os.path.isfile(component_path):
                            x.update(hash_to_bytes(hash(FileType(component_path))))
                        elif os.path.isdir(component_path):
                            x.update(hash_to_bytes(hash(DirType(component_path))))
                    else:
                        x.update(hash_to_bytes(hash(ValueType(component.text))))
                if component.tag:
                    x.update(hash_to_bytes(hash(ValueType(component.tag))))
                if component.attrib:
                    x.update(hash_to_bytes(hash(ObjectType(dict(component.attrib)))))
        input_file = root.xpath("./Files/Value[@name='xmlInputFileName']")[0]
        x.update(hash_to_bytes(hash(FileType(os.path.join(self.config_dir, input_file.text)))))
        x.update(hash_to_bytes(hash(ValueType(input_file.tag))))
        x.update(hash_to_bytes(hash(ObjectType(dict(input_file.attrib)))))
        digest = x.intdigest()
        return digest

    def save_xml(self, out_path):
        self.config_doc.write(out_path)

    def set_scenario_name(self, new_name):
        scenario_tag = self.config_doc.getroot().find("./Strings/Value[@name='scenarioName']")
        scenario_tag.text = new_name

    def get_scenario_name(self):
        scenario_tag = self.config_doc.getroot().find("./Strings/Value[@name='scenarioName']")
        return scenario_tag.text

    def set_max_parallelism(self, new_max):
        par_tag = self.config_doc.getroot().find("./Ints/Value[@name='max-parallelism']")
        par_tag.text = str(new_max)

    def set_file(self, file_tag, write=None, append_scenario=None, path=None):
        file_elem = self.config_doc.getroot().find(f"./Files/Value[@name='{file_tag}']")
        if write is not None:
            file_elem.set("write-output", str(write))
        if append_scenario is not None:
            file_elem.set("append-scenario-name", str(append_scenario))
        if path is not None:
            file_elem.text = path

    def set_xmldb_output(self, write=None, append_scenario=None, path=None):
        self.set_file("xmldb-location", write, append_scenario, path)

    def set_restart_output(self, write=None, append_scenario=None, path=None):
        self.set_file("restart", write, append_scenario, path)

    def disable_outputs(self):
        for f in self.config_doc.getroot().iterfind("./Files/*[@write-output='1']"):
            f.set('write-output', "0")

    def set_batch_mode(self, new_mode):
        batch_flag_elem = self.config_doc.getroot().find("./Bools/Value[@name='BatchMode']")
        batch_flag_elem.text = str(new_mode)

    def set_target_finder_mode(self, new_mode, tf_config=None):
        tf_flag_elem = self.config_doc.getroot().find("./Bools/Value[@name='find-path']")
        tf_flag_elem.text = str(new_mode)
        if tf_config is not None:
            tf_policy_elem = self.config_doc.getroot().find("./Files/Value[@name='policy-target-file']")
            tf_policy_elem.text = tf_config

    def clear_scenario_components(self):
        scn_components = self.config_doc.getroot().find("./ScenarioComponents")
        ET.strip_elements(scn_components, '*', ET.Comment)

    def add_scenario_components(self, new_comps):
        scn_components = self.config_doc.getroot().find("./ScenarioComponents")
        for comp in new_comps:
            scn_components.append(deepcopy(comp))

    def change_base_input_path(self, new_base, fix_climate_xml = True):
        for f in self.config_doc.getroot().xpath("./Files/Value[@name='xmlInputFileName' or @name='policy-target-file' or @name='GHGInputFileName']"):
            f.text = f.text.replace("..", new_base)
        for f in self.config_doc.getroot().iterfind("./ScenarioComponents/Value"):
            f.text = f.text.replace("..", new_base)
        if fix_climate_xml:
            parser = ET.XMLParser(strip_cdata=False)
            climate_xml_path = self.config_doc.getroot().find("./ScenarioComponents/Value[@name='climate']").text
            climate_xml = ET.parse(climate_xml_path, parser)
            for f in climate_xml.xpath("//*[starts-with(text(), '..')]"):
                f.text = f.text.replace("..", new_base)
            climate_xml.write(climate_xml_path)
