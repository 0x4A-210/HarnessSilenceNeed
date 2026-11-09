from scheme_v8.budget import Budget
from scheme_v8.context.reader import load_case
from scheme_v8.llm.attribution.retrieval import initial_packet
from scheme_v8.llm.build_facts import condition_stack, macros_of
from scheme_v8.util import PROJECT_ROOT, load_config


BEFORE = '''#ifndef LIB_H
#define LIB_H
int feature(void) { return 1; }
#if FEATURE_EXTRA
int extra(void) { return 1; }
#endif
#endif
'''
AFTER = BEFORE.replace('int extra(void) { return 1; }', 'int extra(void) { return 2; }')
BUILD = '''#!/bin/bash -eu
mkdir -p out-build
./configure --disable-shared
$CC $CFLAGS -DFUZZ_MODE=1 -c lib.c -o out-build/lib.o
$CXX $CXXFLAGS fuzz.c ./modules/engine/.libs/libengine.a ./vendor/other/missing.a -o $OUT/fuzz
cp $SRC/*.dict $OUT/
zip -r seed.zip tests/*.ini
./scripts/fuzz_build.sh
sed -i 's/option A/option A disabled/' config/settings.dfa
'''
EXTRA = {
    'input/source/config.h': '#define FEATURE_EXTRA 0\n',
    'input/source/configure.ac': 'AC_INIT([lib])\n',
    'input/source/vendor/engine/README': 'moved here\n',
    'input/source/config/settings.dfa': 'option A\n',
    'input/harness/build.sh': BUILD,
    'input/harness/fuzz.dict': 'kw="a"\n',
    'input/source/tests/one.ini': '[a]\n',
    'input/source/scripts/fuzz_build.sh': 'cmake -DENABLE_EXTRA=ON .\ncp corpus/*.bin $OUT/\n',
}


def facts_for(make_input):
    root = make_input(BEFORE, AFTER, extra=EXTRA)
    config = load_config(PROJECT_ROOT / 'configs/default.yaml')
    assert config['llm']['program_facts']
    packet, _ = initial_packet(load_case(root), config, Budget(config['whole_budget']))
    return packet


def test_condition_stack_drops_include_guards_and_keeps_active_branch():
    lines = ['#ifndef G_H', '#define G_H', '#if HAVE_A && !defined(NO_B) /* the comment */', '#else', 'x();', '#endif', '#endif']
    stack = condition_stack(lines, 5)
    assert [s['directive'] for s in stack] == ['#ifndef G_H', '#if HAVE_A && !defined(NO_B) /* the comment */']
    assert stack[0]['include_guard'] and stack[1]['active_branch'] == '#else'
    assert macros_of(stack[1]['directive']) == ['HAVE_A', 'NO_B']


def test_compile_time_context_and_macro_definition(make_input):
    packet = facts_for(make_input)
    facts = packet['program_facts']
    ctx = facts['compile_time_context']
    assert [c['directive'] for c in ctx[0]['enclosing_conditions']] == ['#if FEATURE_EXTRA']
    defs = facts['macro_definitions']['FEATURE_EXTRA']
    assert defs[0]['path'] == 'input/source/config.h' and defs[0]['text'] == '#define FEATURE_EXTRA 0'
    # the supporting lines are citable evidence units
    paths = {e['path'] for e in packet['evidence']}
    assert 'input/source/config.h' in paths


def test_recipe_settings_capture_flags_options_and_source_edits(make_input):
    settings = facts_for(make_input)['program_facts']['build_recipe_settings']
    kinds = {s['text'].split()[0]: s['kind'] for s in settings}
    assert any('--disable-shared' in k for k in kinds['./configure'])
    assert any('-DFUZZ_MODE=1' in k for k in kinds['$CC'])
    assert 'build_time_source_edit' in kinds['sed']


def test_build_path_checks_report_missing_source_directory_with_hint(make_input):
    checks = {c['path']: c for c in facts_for(make_input)['program_facts']['build_path_checks']}
    engine = checks['modules/engine/.libs/libengine.a']
    assert engine['status'] == 'missing' and engine['first_missing'] == 'modules'
    assert engine['same_name_elsewhere'] == ['vendor/engine']
    assert checks['out-build/lib.o']['status'] == 'build_directory_created_by_recipe'
    assert 'configure' not in checks or checks['configure']['status'] != 'missing'
    assert checks['vendor/other/missing.a']['status'] == 'missing'


def test_change_inside_else_branch_reports_active_branch(make_input):
    before = '#if USE_FAST_PATH\nint f(void){return 0;}\n#else\nint f(void){return 1;}\n#endif\n'
    after = before.replace('return 1;', 'return 2;')
    root = make_input(before, after, extra={'input/source/opts.h': '#define USE_FAST_PATH 1\n'})
    config = load_config(PROJECT_ROOT / 'configs/default.yaml')
    packet, _ = initial_packet(load_case(root), config, Budget(config['whole_budget']))
    cond = packet['program_facts']['compile_time_context'][0]['enclosing_conditions'][0]
    assert cond['directive'] == '#if USE_FAST_PATH' and cond['active_branch'] == '#else' and cond['branch_line'] == 3
    assert packet['program_facts']['macro_definitions']['USE_FAST_PATH'][0]['text'] == '#define USE_FAST_PATH 1'


def test_existing_paths_globs_and_src_files_are_reported_affirmatively(make_input):
    checks = {c['path']: c for c in facts_for(make_input)['program_facts']['build_path_checks']}
    assert checks['$SRC/*.dict']['status'] == 'harness_file'
    assert checks['tests/*.ini']['status'] == 'exists' and checks['tests/*.ini']['glob_matches'] == 1
    assert checks['fuzz.c']['status'] == 'harness_file'


def test_source_tree_script_invoked_by_recipe_is_scanned(make_input):
    facts = facts_for(make_input)['program_facts']
    delegated = [s for s in facts['build_recipe_settings'] if s['path'] == 'input/source/scripts/fuzz_build.sh']
    assert delegated and any('-DENABLE_EXTRA=ON' in k for k in delegated[0]['kind'])
    corpus = [c for c in facts['build_path_checks'] if c['path'] == 'corpus/*.bin']
    assert corpus and corpus[0]['status'] == 'missing'

