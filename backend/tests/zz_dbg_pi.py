import sys
import core.package_installer as pi

def test_dbg_pi_state():
    d = pi.docker
    sm = sys.modules.get("docker")
    print("DBG pi.docker id:", id(d), "errors:", d.errors)
    print("DBG sys.modules[docker] id:", id(sm))
    print("DBG same object:", d is sm)
    try:
        print("DBG ImageNotFound class:", d.errors.ImageNotFound)
    except Exception as ex:
        print("DBG err:", ex)
