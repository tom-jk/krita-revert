### File Revert plugin for Krita
Add a Revert action to the File Menu. Closes and reopens the document with the same views.

_feedback welcome._

#### Installation

##### Requirements
Compatible: Krita 5.3
Not tested: Krita 5.2 and earlier
Not compatible: Krita 6

Tested on Linux, but expected to work on Windows and Mac.

##### Instructions
Install in Krita following [these instructions](https://docs.krita.org/en/user_manual/python_scripting/install_custom_python_plugin.html). The revert action will be added to the File menu, and can also be added to toolbars with Settings → Configure Toolbars.

#### Limitations:
- doesn't restore a view's fit view/width/height zoom setting, only the zoom value.

#### History

##### v1.0.0
Initial release
