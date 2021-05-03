# 2开头的错误代码第二位代表错误等级
# 0. 严重错误; 1. 普通错误; 2. 规则错误; 3. 一般信息; 4. 未知错误
class RETCODE:
    OK                  = "0000" # 正常
    DBERR               = "2000" # 数据库异常
    THIRDERR            = "2001" # 第三方异常
    DATAERR             = "2002" # 数据异常
    IOERR               = "2003" # IO异常

    LOGINERR            = "2100" # 登陆错误
    PARAMERR            = "2101" # 参数错误
    USERERR             = "2102" # 用户异常
    ROLEERR             = "2103" # 权限错误
    PWDERR              = "2104" # 密码错误
    VERIFYERR           = "2105" # 验证错误

    REQERR              = "2200" # 请求错误

    NODATA              = "2300" # 无数据
    UNDERDEBUG          = "2301" # debug模式下无法使用

    UNKOWNERR           = "2400" # 未知错误