#!/usr/bin/env python3

import os
import signal

from shell_helpers import LF

class PathProperties:
    default_c_std = 'c11'
    default_cxx_std = 'c++17'
    # All new properties must be listed here or else you get an error.
    default_properties = {
        'allowed_archs': None,
        # The example uses aarch32 instructions which are not present in ARMv7.
        # Therefore, it cannot be run in baremetal ARMv7 CPUs.
        # User mode simulation however seems to enable aarch32 so these run fine.
        'arm_aarch32': False,
        # Examples that can be built in baremetal.
        'baremetal': False,
        'c_std': default_c_std,
        'cc_flags': [
            '-Wall', LF,
            '-Werror', LF,
            '-Wextra', LF,
            '-Wno-unused-function', LF,
            '-ggdb3', LF,
            # PIE causes the following problems:
            # * QEMU GDB step debug does not find breakpoints:
            #   https://stackoverflow.com/questions/51310756/how-to-gdb-step-debug-a-dynamically-linked-executable-in-qemu-user-mode/51343326#51343326
            # * when writing assembly code, we have to constantly think about it:
            #   https://stackoverflow.com/questions/2463150/what-is-the-fpie-option-for-position-independent-executables-in-gcc-and-ld/51308031#51308031
            # As of lkmc 91986fb2955f96e06d1c5ffcc5536ba9f0af1fd9, our Buildroot toolchain
            # does not have it enabled by default, but the Ubuntu 18.04 host toolchain does.
            '-fno-pie', LF,
            '-no-pie', LF,
        ],
        'cc_flags_after': ['-lm', LF],
        'cc_pedantic': True,
        'cxx_std': default_cxx_std,
        'disrupts_system': False,
        # Expected program exit status. When signals are raised, this refers
        # to the native exit status. as reported by Bash #?.
        'exit_status': 0,
        'extra_objs': [],
        # Explicitly don't add the baremetal bootloader object which normally gets automatically
        # added to baremetal examples.
        'extra_objs_disable_baremetal_bootloader': False,
        # We should get rid of this if we ever properly implement dependency graphs.
        'extra_objs_lkmc_common': False,
        'gem5_unimplemented_instruction': False,
        'qemu_unimplemented_instruction': False,
        # For some reason QEMU fails with SIGSEGV on int syscalls in x86_64.
        'qemu_x86_64_int_syscall': False,
        'interactive': False,
        # The script takes a perceptible amount of time to run. Possibly an infinite loop.
        'more_than_1s': False,
        # The path should not be built. E.g., it is symlinked into multiple archs.
        'no_build': False,
        # The path does not generate an executable in itself, e.g.
        # it only generates intermediate object files. Therefore it
        # should not be run while testing.
        'no_executable': False,
        # The script requires a non-trivial argument to be passed to run properly.
        'requires_argument': False,
        'requires_dynamic_library': False,
        'requires_m5ops': False,
        # gem5 fatal: syscall getcpu (#168) unimplemented.
        'requires_syscall_getcpu': False,
        'requires_semihosting': False,
        # Requires certain of our custom kernel modules to be inserted to run.
        'requires_kernel_modules': False,
        # The example requires sudo, which usually implies that it can do something
        # deeply to the system it runs on, which would preventing further interactive
        # or test usage of the system, for example poweroff or messing up the GUI.
        'requires_sudo': False,
        # The signal received is generated by the OS implicitly rather than explicitly
        # done sith signal(), e.g. Illegal instruction or sigsegv.
        # Therefore, it won't behave in the same way in baremetal. aarch64 already
        # has an exception handler which we could use but arm doesn't and the IP
        # goes astray, so let's just skip this for now.
        'signal_generated_by_os': False,
        'signal_received': None,
        # We were lazy to properly classify why we are skipping these tests.
        # TODO get it done.
        'skip_run_unclassified': False,
        # Aruments added automatically to run when running tests,
        # but not on manual running.
        'test_run_args': {},
        # Examples that can be built in userland.
        'userland': False,
    }

    '''
    Encodes properties of userland and baremetal paths.
    For directories, it applies to all files under the directory.
    Used to determine how to build and test the examples.
    '''
    def __init__(
        self,
        properties
    ):
        for key in properties:
            if not key in self.default_properties:
                raise ValueError('Unknown key: {}'.format(key))
        self.properties = properties.copy()

    def __getitem__(self, key):
        return self.properties[key]

    def __repr__(self):
        return str(self.properties)

    def set_path_components(self, path_components):
        self.path_components = path_components

    def should_be_built(
        self,
        env,
        link=False,
    ):
        ext = os.path.splitext(self.path_components[-1])[1]
        return (
            not (
                len(self.path_components) > 1 and \
                self.path_components[1] == 'libs' and \
                not env['package_all'] and \
                not self.path_components[2] in env['package']
            ) and
            not self['no_build'] and
            (
                self['allowed_archs'] is None or
                env['arch'] in self['allowed_archs']
            ) and
            not (
                (
                    env['mode'] == 'userland' and
                    (
                        not self['userland'] or
                        not ext in env['build_in_exts']
                    )
                ) or
                (
                    env['mode'] == 'baremetal' and (
                        not self['baremetal'] or
                        not ext in env['baremetal_build_in_exts']
                    )
                )
            ) and
            not (
                link and
                self['no_executable']
            )
        )

    def should_be_tested(self, env):
        return (
            self.should_be_built(
                env,
            ) and
            not (
                env['mode'] == 'baremetal' and (
                    self['arm_aarch32'] or
                    self['signal_generated_by_os']
                )
            ) and
            not self['disrupts_system'] and
            not self['interactive'] and
            not self['more_than_1s'] and
            not self['no_executable'] and
            not self['requires_argument'] and
            not self['requires_kernel_modules'] and
            not self['requires_sudo'] and
            not self['skip_run_unclassified'] and
            not self['qemu_x86_64_int_syscall'] and
            not (
                env['emulator'] == 'gem5' and
                (
                    self['gem5_unimplemented_instruction'] or
                    # gem5 does not report signals properly.
                    self['signal_received'] is not None or
                    self['requires_dynamic_library'] or
                    self['requires_semihosting'] or
                    self['requires_syscall_getcpu']
                )
            ) and
            not (
                env['emulator'] == 'qemu' and
                (
                    self['requires_m5ops'] or
                    env['mode'] == 'baremetal' and (
                        self['qemu_unimplemented_instruction']
                    )
                )
            )
        )

    def _update_dict(self, other_tmp_properties, key):
        if key in self.properties and key in other_tmp_properties:
            other_tmp_properties[key] = {
                **self.properties[key],
                **other_tmp_properties[key]
            }

    def _update_list(self, other_tmp_properties, key):
        if key in self.properties and key in other_tmp_properties:
            other_tmp_properties[key] = \
                self.properties[key] + \
                other_tmp_properties[key]

    def update(self, other):
        other_tmp_properties = other.properties.copy()
        self._update_list(other_tmp_properties, 'cc_flags')
        self._update_list(other_tmp_properties, 'cc_flags_after')
        self._update_list(other_tmp_properties, 'extra_objs')
        self._update_dict(other_tmp_properties, 'test_run_args')
        return self.properties.update(other_tmp_properties)

class PrefixTree:
    def __init__(self, path_properties_dict=None, children=None):
        if path_properties_dict is None:
            path_properties_dict = {}
        if children is None:
            children = {}
        self.children = children
        self.path_properties = PathProperties(path_properties_dict)

    @staticmethod
    def make_from_tuples(tuples):
        def tree_from_tuples(tuple_):
            if not type(tuple_) is tuple:
                tuple_ = (tuple_, {})
            cur_properties, cur_children = tuple_
            return PrefixTree(cur_properties, cur_children)
        top_tree = tree_from_tuples(tuples)
        todo_trees = [top_tree]
        while todo_trees:
            cur_tree = todo_trees.pop()
            cur_children = cur_tree.children
            for child_key in cur_children:
                new_tree = tree_from_tuples(cur_children[child_key])
                cur_children[child_key] = new_tree
                todo_trees.append(new_tree)
        return top_tree

def get(path):
    cur_node = path_properties_tree
    path_components = path.split(os.sep)
    path_properties = PathProperties(cur_node.path_properties.properties.copy())
    for path_component in path_components:
        if path_component in cur_node.children:
            cur_node = cur_node.children[path_component]
            path_properties.update(cur_node.path_properties)
        else:
            break
    path_properties.set_path_components(path_components)
    return path_properties

gnu_extension_properties = {
    'c_std': 'gnu11',
    'cc_pedantic': False,
    'cxx_std': 'gnu++17'
}
freestanding_properties = {
    'baremetal': False,
    'cc_flags': [
        '-ffreestanding', LF,
        '-nostdlib', LF,
        '-static', LF,
    ],
    'extra_objs_lkmc_common': False,
}
# See: https://cirosantilli.com/linux-kernel-module-cheat#path-properties
path_properties_tuples = (
    PathProperties.default_properties,
    {
        'baremetal': (
            {
                'baremetal': True,
            },
            {
                'arch': (
                    {},
                    {
                        'arm': (
                            {'allowed_archs': {'arm'}},
                            {
                                'multicore.S': {'test_run_args': {'cpus': 2}},
                                'no_bootloader': (
                                    {'extra_objs_disable_baremetal_bootloader': True},
                                    {
                                        'gem5_exit.S': {'requires_m5ops': True},
                                        'semihost_exit.S': {'requires_semihosting': True},
                                    }
                                ),
                                'return1.S': {'exit_status': 1},
                                'semihost_exit.S': {'requires_semihosting': True},
                            },

                        ),
                        'aarch64': (
                            {'allowed_archs': {'aarch64'}},
                            {
                                'multicore.S': {'test_run_args': {'cpus': 2}},
                                'no_bootloader': (
                                    {'extra_objs_disable_baremetal_bootloader': True},
                                    {
                                        'gem5_exit.S': {'requires_m5ops': True},
                                        'semihost_exit.S': {'requires_semihosting': True},
                                        'wfe_loop.S': {'more_than_1s': True},
                                    }
                                ),
                                'return1.S': {'exit_status': 1},
                                'semihost_exit.S': {'requires_semihosting': True},
                                'svc.c': {'cc_pedantic': False},
                                'timer.c': {'skip_run_unclassified': True},
                            },
                        )
                    }
                ),
                'lib': {'no_executable': True},
                'getchar.c': {'interactive': True},
            }
        ),
        'kernel_modules': (
            {},
            {
                'float.c': {'allowed_archs': 'x86_64'}
            },
        ),
        'lkmc.c': {
            'baremetal': True,
            'userland': True,
        },
        'userland': (
            {
                'userland': True,
            },
            {
                'arch': (
                    {
                        'baremetal': True,
                        'extra_objs_lkmc_common': True,
                    },
                    {
                        'arm': (
                            {
                                'allowed_archs': {'arm'},
                                'cc_flags': [
                                    # To prevent:
                                    # > vfp.S: Error: selected processor does not support <FPU instruction> in ARM mode
                                    # https://stackoverflow.com/questions/41131432/cross-compiling-error-selected-processor-does-not-support-fmrx-r3-fpexc-in/52875732#52875732
                                    # We aim to take the most extended mode currently available that works on QEMU.
                                    '-Xassembler', '-mfpu=crypto-neon-fp-armv8.1', LF,
                                    '-Xassembler', '-meabi=5', LF,
                                    # Treat inline assembly as arm instead of thumb
                                    # The opposite of -mthumb.
                                    '-marm', LF,
                                    # Make gcc generate .syntax unified for inline assembly.
                                    # However, it gets ignored if -marm is given, which a GCC bug that was recently fixed:
                                    # https://stackoverflow.com/questions/54078112/how-to-write-syntax-unified-ual-armv7-inline-assembly-in-gcc/54132097#54132097
                                    # So we just write divided inline assembly for now.
                                    '-masm-syntax-unified', LF,
                                ]
                            },
                            {
                                'inline_asm': (
                                    {
                                    },
                                    {
                                        'freestanding': freestanding_properties,
                                    },
                                ),
                                'freestanding': freestanding_properties,
                                'lkmc_assert_eq_fail.S': {'signal_received': signal.Signals.SIGABRT},
                                'lkmc_assert_memcmp_fail.S': {'signal_received': signal.Signals.SIGABRT},
                                'udf.S': {
                                    'signal_generated_by_os': True,
                                    'signal_received': signal.Signals.SIGILL,
                                },
                                'vcvta.S': {
                                    'arm_aarch32': True,
                                    'gem5_unimplemented_instruction': True,
                                },
                            }
                        ),
                        'aarch64': (
                            {
                                'allowed_archs': {'aarch64'},
                            },
                            {
                                'inline_asm': (
                                    {
                                    },
                                    {
                                        'freestanding': freestanding_properties,
                                    },
                                ),
                                'freestanding': freestanding_properties,
                                'lkmc_assert_eq_fail.S': {'signal_received': signal.Signals.SIGABRT},
                                'lkmc_assert_memcmp_fail.S': {'signal_received': signal.Signals.SIGABRT},
                                'udf.S': {
                                    'signal_generated_by_os': True,
                                    'signal_received': signal.Signals.SIGILL,
                                },
                                'sve.S': {'gem5_unimplemented_instruction': True}
                            }
                        ),
                        'x86_64': (
                            {'allowed_archs': {'x86_64'}},
                            {
                                'freestanding': (
                                    freestanding_properties,
                                    {
                                        'linux': (
                                            {},
                                            {
                                                'int_system_call.S': {'qemu_x86_64_int_syscall': True},
                                            }
                                        ),
                                    }
                                ),
                                'inline_asm': (
                                    {},
                                    {
                                        'freestanding': freestanding_properties,
                                    }
                                ),
                                'intrinsics': (
                                    {},
                                    {
                                        'rdtscp.c': {
                                            'gem5_unimplemented_instruction': True,
                                            'qemu_unimplemented_instruction': True,
                                        },
                                    }
                                ),
                                'div_overflow.S': {'signal_received': signal.Signals.SIGFPE},
                                'div_zero.S': {'signal_received': signal.Signals.SIGFPE},
                                'lkmc_assert_eq_fail.S': {'signal_received': signal.Signals.SIGABRT},
                                'lkmc_assert_memcmp_fail.S': {'signal_received': signal.Signals.SIGABRT},
                                'popcnt.S': {'qemu_unimplemented_instruction': True},
                                'rdrand.S': {
                                    'gem5_unimplemented_instruction': True,
                                    'qemu_unimplemented_instruction': True,
                                },
                                'rdtscp.S': {'qemu_unimplemented_instruction': True},
                                'ring0.c': {'signal_received': signal.Signals.SIGSEGV},
                                'vfmadd132pd.S': {
                                    'gem5_unimplemented_instruction': True,
                                    'qemu_unimplemented_instruction': True,
                                },
                            }
                        ),
                        'lkmc_assert_fail.S': {
                            'signal_received': signal.Signals.SIGABRT,
                        },
                    }
                ),
                'c': (
                    {
                        'baremetal': True,
                    },
                    {
                        'abort.c': {
                            'signal_received': signal.Signals.SIGABRT,
                        },
                        'assert_fail.c': {
                            'signal_received': signal.Signals.SIGABRT,
                        },
                        'exit1.c': {'exit_status': 1},
                        'exit2.c': {'exit_status': 2},
                        'false.c': {'exit_status': 1},
                        'file_write_read.c': {'baremetal': False},
                        'getchar.c': {'interactive': True},
                        'infinite_loop.c': {'more_than_1s': True},
                        'out_of_memory.c': {'disrupts_system': True},
                        'return1.c': {'exit_status': 1},
                        'return2.c': {'exit_status': 2},
                    }
                ),
                'cpp': (
                    {},
                    {
                        'atomic.cpp': {
                            'test_run_args': {'cpus': 3},
                            # LDADD from LSE
                            'gem5_unimplemented_instruction': True,
                        },
                        'count.cpp': {'more_than_1s': True},
                        'sleep_for.cpp': {
                            'more_than_1s': True,
                        },
                    },
                ),
                'gcc': (
                    gnu_extension_properties,
                    {
                        'openmp.c': {'cc_flags': ['-fopenmp', LF]},
                    }
                ),
                'gdb_tests': {'baremetal': True},
                'kernel_modules': {**gnu_extension_properties, **{'requires_kernel_modules': True}},
                'libs': (
                    {'requires_dynamic_library': True},
                    {
                        'libdrm': {'requires_sudo': True},
                    }
                ),
                'linux': (
                    gnu_extension_properties,
                    {
                        'ctrl_alt_del.c': {'requires_sudo': True},
                        'init_env_poweroff.c': {'requires_sudo': True},
                        'myinsmod.c': {'requires_sudo': True},
                        'myrmmod.c': {'requires_sudo': True},
                        'pagemap_dump.c': {'requires_argument': True},
                        'poweroff.c': {'requires_sudo': True},
                        'proc_events.c': {'requires_sudo': True},
                        'proc_events.c': {'requires_sudo': True},
                        'sched_getaffinity.c': {'requires_syscall_getcpu': True},
                        'sched_getaffinity_threads.c': {
                            'more_than_1s': True,
                            'requires_syscall_getcpu': True,
                        },
                        'time_boot.c': {'requires_sudo': True},
                        'virt_to_phys_user.c': {'requires_argument': True},
                    }
                ),
                'posix': (
                    {},
                    {
                        'count.c': {'more_than_1s': True},
                        'count_to.c': {'more_than_1s': True},
                        'kill.c': {
                            'baremetal': True,
                            'signal_received': signal.Signals.SIGHUP,
                        },
                        'pthread_count.c': {
                            'more_than_1s': True,
                            'test_run_args': {'cpus': 2},
                        },
                        'pthread_self.c': {
                            'test_run_args': {'cpus': 2},
                        },
                        'sleep_forever.c': {'more_than_1s': True},
                        'virt_to_phys_test.c': {'more_than_1s': True},
                    }
                ),
            }
        ),
    }
)
path_properties_tree = PrefixTree.make_from_tuples(path_properties_tuples)
