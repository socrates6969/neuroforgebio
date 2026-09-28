namespace Example
{
    // Fixture: Foo.cs and Bar.cs share the same GUID in their .meta files. checkMetaFiles() must
    // flag this as a duplicate GUID (two assets with the same identity corrupt Unity's asset
    // database and any hash-addressed reference to either asset).
    public class Foo
    {
    }
}
