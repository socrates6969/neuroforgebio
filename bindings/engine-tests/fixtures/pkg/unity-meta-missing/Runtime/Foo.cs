namespace Example
{
    // Fixture: Foo.cs has a .meta, but Bar.cs (sibling file) does not. Since at least one .meta
    // exists in the tree, checkMetaFiles() switches to the strict 'present' state and must flag
    // Bar.cs as missing.
    public class Foo
    {
    }
}
