"""
Pokemon Essentials 세이브 파일용 Ruby Marshal 파서.
rubymarshal 라이브러리의 순환 참조 오류를 해결하기 위한 커스텀 구현.
"""

import struct


class RubySymbol:
    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return f":{self.name}"

    def __str__(self):
        return self.name

    def __eq__(self, other):
        if isinstance(other, RubySymbol):
            return self.name == other.name
        if isinstance(other, str):
            return self.name == other
        return False

    def __hash__(self):
        return hash(self.name)


class RubyObject:
    def __init__(self, class_name):
        self.class_name = class_name
        self.attributes = {}

    def __repr__(self):
        return f"<{self.class_name}>"

    def get(self, key, default=None):
        if isinstance(key, str) and not key.startswith("@"):
            key = f"@{key}"
        return self.attributes.get(key, default)


class RubyUserDef:
    def __init__(self, class_name, data):
        self.class_name = class_name
        self.data = data

    def __repr__(self):
        return f"<UserDef:{self.class_name}>"


class MarshalReader:
    """Ruby Marshal 4.8 포맷 리더. 순환 참조를 안전하게 처리합니다."""

    def __init__(self, data):
        self.data = data
        self.pos = 0
        self.objects = []    # object references (@)
        self.symbols = []    # symbol references (;)

    def read_byte(self):
        b = self.data[self.pos]
        self.pos += 1
        return b

    def read_bytes(self, n):
        result = self.data[self.pos:self.pos + n]
        self.pos += n
        return result

    def read_long(self):
        """Ruby Marshal의 특수 정수 인코딩"""
        c = struct.unpack('b', self.read_bytes(1))[0]
        if c == 0:
            return 0
        if 5 > c > 0:
            n = 0
            for i in range(c):
                n |= self.read_byte() << (8 * i)
            return n
        if -5 < c < 0:
            n = -1
            for i in range(-c):
                n &= ~(0xff << (8 * i))
                n |= self.read_byte() << (8 * i)
            return n
        return c - 5 if c > 0 else c + 5

    def read_string_raw(self):
        length = self.read_long()
        return self.read_bytes(length)

    def _register_object(self, obj):
        self.objects.append(obj)
        return obj

    def read_value(self):
        type_byte = chr(self.read_byte())

        if type_byte == '0':  # nil
            return None

        elif type_byte == 'T':  # true
            return True

        elif type_byte == 'F':  # false
            return False

        elif type_byte == 'i':  # integer
            return self.read_long()

        elif type_byte == 'f':  # float
            s = self.read_string_raw().decode('utf-8')
            self._register_object(float(s))
            return float(s)

        elif type_byte == ':':  # symbol
            name = self.read_string_raw().decode('utf-8', errors='replace')
            sym = RubySymbol(name)
            self.symbols.append(sym)
            return sym

        elif type_byte == ';':  # symbol reference
            idx = self.read_long()
            if idx < len(self.symbols):
                return self.symbols[idx]
            return RubySymbol(f"__unknown_sym_{idx}")

        elif type_byte == '@':  # object reference
            idx = self.read_long()
            if idx < len(self.objects):
                return self.objects[idx]
            # 참조 대상이 아직 없으면 플레이스홀더 반환 (순환 참조)
            return None

        elif type_byte == '"':  # string
            raw = self.read_string_raw()
            try:
                s = raw.decode('utf-8')
            except UnicodeDecodeError:
                s = raw.decode('latin-1', errors='replace')
            self._register_object(s)
            return s

        elif type_byte == 'I':  # instance variables (보통 string + encoding)
            obj = self.read_value()
            count = self.read_long()
            for _ in range(count):
                key = self.read_value()
                val = self.read_value()
                # string에 encoding 정보 붙는 경우
                if isinstance(obj, RubyObject):
                    key_str = str(key)
                    obj.attributes[key_str] = val
            return obj

        elif type_byte == '[':  # array
            length = self.read_long()
            arr = []
            self._register_object(arr)
            for _ in range(length):
                arr.append(self.read_value())
            return arr

        elif type_byte == '{':  # hash
            length = self.read_long()
            h = {}
            self._register_object(h)
            for _ in range(length):
                key = self.read_value()
                val = self.read_value()
                # dict 키로 사용 가능하게 변환
                if isinstance(key, RubySymbol):
                    h[key.name] = val
                elif isinstance(key, (str, int, float, bool)):
                    h[key] = val
                else:
                    h[str(key)] = val
            return h

        elif type_byte == 'o':  # object
            class_sym = self.read_value()
            class_name = str(class_sym) if class_sym else "Unknown"
            obj = RubyObject(class_name)
            self._register_object(obj)
            count = self.read_long()
            for _ in range(count):
                key = self.read_value()
                val = self.read_value()
                key_str = str(key)
                obj.attributes[key_str] = val
            return obj

        elif type_byte == 'C':  # subclass of core type
            class_sym = self.read_value()
            obj = self.read_value()
            return obj

        elif type_byte == 'u':  # user defined (dump/load)
            class_sym = self.read_value()
            class_name = str(class_sym)
            raw = self.read_string_raw()
            ud = RubyUserDef(class_name, raw)
            self._register_object(ud)
            return ud

        elif type_byte == 'U':  # user marshal
            class_sym = self.read_value()
            class_name = str(class_sym)
            obj = RubyObject(class_name)
            self._register_object(obj)
            data = self.read_value()
            if isinstance(data, dict):
                obj.attributes = {str(k): v for k, v in data.items()}
            elif isinstance(data, RubyObject):
                obj.attributes = data.attributes
            else:
                obj.attributes["_data"] = data
            return obj

        elif type_byte == 'l':  # bignum
            sign = chr(self.read_byte())
            length = self.read_long()
            data = self.read_bytes(length * 2)
            n = int.from_bytes(data, 'little')
            if sign == '-':
                n = -n
            self._register_object(n)
            return n

        elif type_byte == 'e':  # extended module
            module_sym = self.read_value()
            return self.read_value()

        elif type_byte == '/':  # regexp
            raw = self.read_string_raw()
            flags = self.read_byte()
            s = raw.decode('utf-8', errors='replace')
            self._register_object(s)
            return s

        elif type_byte == 'c':  # class
            name = self.read_string_raw().decode('utf-8', errors='replace')
            self._register_object(name)
            return name

        elif type_byte == 'm':  # module
            name = self.read_string_raw().decode('utf-8', errors='replace')
            self._register_object(name)
            return name

        elif type_byte == 'S':  # struct
            class_sym = self.read_value()
            class_name = str(class_sym)
            obj = RubyObject(class_name)
            self._register_object(obj)
            count = self.read_long()
            for _ in range(count):
                key = self.read_value()
                val = self.read_value()
                obj.attributes[str(key)] = val
            return obj

        elif type_byte == '}':  # hash with default
            length = self.read_long()
            h = {}
            self._register_object(h)
            for _ in range(length):
                key = self.read_value()
                val = self.read_value()
                if isinstance(key, RubySymbol):
                    h[key.name] = val
                else:
                    h[str(key)] = val
            default = self.read_value()  # default value
            return h

        else:
            raise ValueError(
                f"Unknown marshal type '{type_byte}' (0x{ord(type_byte):02x}) at position {self.pos - 1}"
            )

    def load(self):
        major = self.read_byte()
        minor = self.read_byte()
        if major != 4 or minor != 8:
            raise ValueError(f"Unsupported marshal version {major}.{minor}")
        return self.read_value()


def load(filepath):
    """Ruby Marshal 파일을 로드합니다."""
    with open(filepath, "rb") as f:
        data = f.read()
    reader = MarshalReader(data)
    return reader.load()
