import pymysql

# Django's mysql backend expects mysqlclient (a C extension); PyMySQL is
# pure Python and works everywhere mysqlclient's build toolchain doesn't
# (no local MySQL client headers/compiler needed) -- this shim makes
# django.db.backends.mysql use it transparently.
pymysql.install_as_MySQLdb()
