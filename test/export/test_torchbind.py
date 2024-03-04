# Owner(s): ["oncall: export"]

import torch
import torch.testing._internal.torchbind_impls  # noqa: F401
from torch._higher_order_ops.torchbind import enable_torchbind_tracing
from torch.export import export
from torch.testing._internal.common_utils import run_tests, skipIfTorchDynamo, TestCase


@skipIfTorchDynamo("torchbind not supported with dynamo yet")
class TestExportTorchbind(TestCase):
    def setUp(self):
        @torch._library.impl_abstract_class("_TorchScriptTesting::_Foo")
        class FakeFoo:
            def __init__(self, x, y):
                self.x = x
                self.y = y

            @classmethod
            def from_real(cls, foo):
                x, y = foo.__get_metadata__()
                return cls(x, y)

            def add_tensor(self, z):
                return (self.x + self.y) * z

    def tearDown(self):
        torch._library.abstract_impl_class.deregister_abstract_impl(
            "_TorchScriptTesting::_Foo"
        )

    def _test_export_same_as_eager(self, f, args, kwargs=None, strict=True):
        kwargs = kwargs or {}
        with enable_torchbind_tracing():
            exported_program = export(f, args, kwargs, strict=strict)
        gm = exported_program.module()
        reversed_kwargs = {key: kwargs[key] for key in reversed(kwargs)}
        self.assertEqual(gm(*args, **kwargs), f(*args, **kwargs))
        self.assertEqual(
            gm(*args, **reversed_kwargs),
            f(*args, **reversed_kwargs),
        )
        return exported_program

    def test_none(self):
        class MyModule(torch.nn.Module):
            def __init__(self):
                super().__init__()
                self.attr = torch.classes._TorchScriptTesting._Foo(10, 20)

            def forward(self, x, n):
                return x + self.attr.add_tensor(x)

        ep = self._test_export_same_as_eager(
            MyModule(), (torch.ones(2, 3), None), strict=False
        )
        self.assertExpectedInline(
            ep.module().code.strip("\n"),
            """\
def forward(self, arg_0, arg_1):
    arg0_1, arg1_1, = fx_pytree.tree_flatten_spec(([arg_0, arg_1], {}), self._in_spec)
    attr_1 = self.attr
    call_torchbind = torch.ops.higher_order.call_torchbind(attr_1, 'add_tensor', arg0_1);  attr_1 = None
    add = torch.ops.aten.add.Tensor(arg0_1, call_torchbind);  arg0_1 = call_torchbind = None
    return pytree.tree_unflatten((add,), self._out_spec)
    """,
        )
        self.assertExpectedInline(
            ep.graph_module.code.strip("\n"),
            """\
def forward(self, attr, arg0_1, arg1_1):
    call_torchbind = torch.ops.higher_order.call_torchbind(attr, 'add_tensor', arg0_1);  attr = None
    add = torch.ops.aten.add.Tensor(arg0_1, call_torchbind);  arg0_1 = call_torchbind = None
    return (add,)
    """,
        )

    def test_attribute(self):
        class MyModule(torch.nn.Module):
            def __init__(self):
                super().__init__()
                self.attr = torch.classes._TorchScriptTesting._Foo(10, 20)

            def forward(self, x):
                return x + self.attr.add_tensor(x)

        ep = self._test_export_same_as_eager(
            MyModule(), (torch.ones(2, 3),), strict=False
        )
        self.assertExpectedInline(
            ep.module().code.strip("\n"),
            """\
def forward(self, arg_0):
    arg0_1, = fx_pytree.tree_flatten_spec(([arg_0], {}), self._in_spec)
    attr_1 = self.attr
    call_torchbind = torch.ops.higher_order.call_torchbind(attr_1, 'add_tensor', arg0_1);  attr_1 = None
    add = torch.ops.aten.add.Tensor(arg0_1, call_torchbind);  arg0_1 = call_torchbind = None
    return pytree.tree_unflatten((add,), self._out_spec)
    """,
        )
        self.assertExpectedInline(
            ep.graph_module.code.strip("\n"),
            """\
def forward(self, attr, arg0_1):
    call_torchbind = torch.ops.higher_order.call_torchbind(attr, 'add_tensor', arg0_1);  attr = None
    add = torch.ops.aten.add.Tensor(arg0_1, call_torchbind);  arg0_1 = call_torchbind = None
    return (add,)
    """,
        )

    def test_attribute_as_custom_op_argument(self):
        class MyModule(torch.nn.Module):
            def __init__(self):
                super().__init__()
                self.attr = torch.classes._TorchScriptTesting._Foo(10, 20)

            def forward(self, x):
                return x + torch.ops._TorchScriptTesting.takes_foo(self.attr, x)

        ep = self._test_export_same_as_eager(
            MyModule(), (torch.ones(2, 3),), strict=False
        )
        self.assertExpectedInline(
            ep.module().code.strip("\n"),
            """\
def forward(self, arg_0):
    arg0_1, = fx_pytree.tree_flatten_spec(([arg_0], {}), self._in_spec)
    attr_1 = self.attr
    takes_foo = torch.ops._TorchScriptTesting.takes_foo.default(attr_1, arg0_1);  attr_1 = None
    add = torch.ops.aten.add.Tensor(arg0_1, takes_foo);  arg0_1 = takes_foo = None
    return pytree.tree_unflatten((add,), self._out_spec)
    """,
        )
        self.assertExpectedInline(
            ep.graph_module.code.strip("\n"),
            """\
def forward(self, attr, arg0_1):
    takes_foo = torch.ops._TorchScriptTesting.takes_foo.default(attr, arg0_1);  attr = None
    add = torch.ops.aten.add.Tensor(arg0_1, takes_foo);  arg0_1 = takes_foo = None
    return (add,)
    """,
        )

    def test_input(self):
        class MyModule(torch.nn.Module):
            def __init__(self):
                super().__init__()

            def forward(self, x, cc):
                return x + cc.add_tensor(x)

        cc = torch.classes._TorchScriptTesting._Foo(10, 20)
        ep = self._test_export_same_as_eager(
            MyModule(), (torch.ones(2, 3), cc), strict=False
        )
        self.assertExpectedInline(
            ep.module().code.strip("\n"),
            """\
def forward(self, arg_0, arg_1):
    arg0_1, arg1_1, = fx_pytree.tree_flatten_spec(([arg_0, arg_1], {}), self._in_spec)
    call_torchbind = torch.ops.higher_order.call_torchbind(arg1_1, 'add_tensor', arg0_1);  arg1_1 = None
    add = torch.ops.aten.add.Tensor(arg0_1, call_torchbind);  arg0_1 = call_torchbind = None
    return pytree.tree_unflatten((add,), self._out_spec)
    """,
        )
        self.assertExpectedInline(
            ep.graph_module.code.strip("\n"),
            """\
def forward(self, arg0_1, arg1_1):
    call_torchbind = torch.ops.higher_order.call_torchbind(arg1_1, 'add_tensor', arg0_1);  arg1_1 = None
    add = torch.ops.aten.add.Tensor(arg0_1, call_torchbind);  arg0_1 = call_torchbind = None
    return (add,)
    """,
        )

    def test_input_as_custom_op_argument(self):
        class MyModule(torch.nn.Module):
            def __init__(self):
                super().__init__()

            def forward(self, x, cc):
                return x + torch.ops._TorchScriptTesting.takes_foo(cc, x)

        cc = torch.classes._TorchScriptTesting._Foo(10, 20)
        ep = self._test_export_same_as_eager(
            MyModule(), (torch.ones(2, 3), cc), strict=False
        )
        self.assertExpectedInline(
            ep.module().code.strip("\n"),
            """\
def forward(self, arg_0, arg_1):
    arg0_1, arg1_1, = fx_pytree.tree_flatten_spec(([arg_0, arg_1], {}), self._in_spec)
    takes_foo = torch.ops._TorchScriptTesting.takes_foo.default(arg1_1, arg0_1);  arg1_1 = None
    add = torch.ops.aten.add.Tensor(arg0_1, takes_foo);  arg0_1 = takes_foo = None
    return pytree.tree_unflatten((add,), self._out_spec)
    """,
        )
        self.assertExpectedInline(
            ep.graph_module.code.strip("\n"),
            """\
def forward(self, arg0_1, arg1_1):
    takes_foo = torch.ops._TorchScriptTesting.takes_foo.default(arg1_1, arg0_1);  arg1_1 = None
    add = torch.ops.aten.add.Tensor(arg0_1, takes_foo);  arg0_1 = takes_foo = None
    return (add,)
    """,
        )

    def test_unlift_custom_obj(self):
        class MyModule(torch.nn.Module):
            def __init__(self):
                super().__init__()
                self.attr = torch.classes._TorchScriptTesting._Foo(10, 20)

            def forward(self, x):
                return x + torch.ops._TorchScriptTesting.takes_foo(self.attr, x)

        m = MyModule()
        input = torch.ones(2, 3)
        with enable_torchbind_tracing():
            ep = torch.export.export(m, (input,), strict=False)

        unlifted = ep.module()
        self.assertExpectedInline(
            unlifted.code.strip("\n"),
            """\
def forward(self, arg_0):
    arg0_1, = fx_pytree.tree_flatten_spec(([arg_0], {}), self._in_spec)
    attr_1 = self.attr
    takes_foo = torch.ops._TorchScriptTesting.takes_foo.default(attr_1, arg0_1);  attr_1 = None
    add = torch.ops.aten.add.Tensor(arg0_1, takes_foo);  arg0_1 = takes_foo = None
    return pytree.tree_unflatten((add,), self._out_spec)
    """,
        )
        self.assertExpectedInline(
            ep.graph_module.code.strip("\n"),
            """\
def forward(self, attr, arg0_1):
    takes_foo = torch.ops._TorchScriptTesting.takes_foo.default(attr, arg0_1);  attr = None
    add = torch.ops.aten.add.Tensor(arg0_1, takes_foo);  arg0_1 = takes_foo = None
    return (add,)
    """,
        )
        self.assertEqual(m(input), unlifted(input))


@skipIfTorchDynamo("torchbind not supported with dynamo yet")
class TestImplAbstractClass(TestCase):
    def tearDown(self):
        torch._library.abstract_impl_class.global_abstract_class_registry.clear()

    def test_impl_abstract_class_no_torch_bind_class(self):
        with self.assertRaisesRegex(RuntimeError, "Tried to instantiate class"):

            @torch._library.impl_abstract_class("_TorchScriptTesting::NOT_A_VALID_NAME")
            class Invalid:
                pass

    def test_impl_abstract_class_no_from_real(self):
        with self.assertRaisesRegex(
            RuntimeError, "must define a classmethod from_real"
        ):

            @torch._library.impl_abstract_class("_TorchScriptTesting::_Foo")
            class InvalidFakeFoo:
                def __init__(self):
                    pass

    def test_impl_abstract_class_from_real_not_classmethod(self):
        with self.assertRaisesRegex(
            RuntimeError, "must define a classmethod from_real"
        ):

            @torch._library.impl_abstract_class("_TorchScriptTesting::_Foo")
            class FakeFoo:
                def __init__(self, x, y):
                    self.x = x
                    self.y = y

                def from_real(self, foo_obj):
                    x, y = foo_obj.__get_metadata__()
                    return FakeFoo(x, y)

    def test_impl_abstract_class_valid(self):
        class FakeFoo:
            def __init__(self, x, y):
                self.x = x
                self.y = y

            @classmethod
            def from_real(cls, foo_obj):
                x, y = foo_obj.__get_metadata__()
                return cls(x, y)

        torch._library.impl_abstract_class("_TorchScriptTesting::_Foo", FakeFoo)

    def test_impl_abstract_class_duplicate_registration(self):
        @torch._library.impl_abstract_class("_TorchScriptTesting::_Foo")
        class FakeFoo:
            def __init__(self, x, y):
                self.x = x
                self.y = y

            @classmethod
            def from_real(cls, foo_obj):
                x, y = foo_obj.__get_metadata__()
                return cls(x, y)

        with self.assertRaisesRegex(RuntimeError, "already registered"):
            torch._library.impl_abstract_class("_TorchScriptTesting::_Foo", FakeFoo)


if __name__ == "__main__":
    run_tests()
