import sys
import math

def calculate_entropy(data):
    if not data:
        return 0
    entropy = 0
    for x in range(256):
        p_x = float(data.count(x)) / len(data)
        if p_x > 0:
            entropy += - p_x * math.log(p_x, 2)
    return entropy

with open(r'C:\Users\hover\Pictures\app\classes.dex', 'rb') as f:
    data = f.read()
    entropy = calculate_entropy(data)
    print(f"文件总熵值: {entropy:.2f}")
    print(f"文件大小: {len(data)} 字节")

    # 检查前1KB的熵值（dex头应该是低熵）
    header_entropy = calculate_entropy(data[:1024])
    print(f"前1KB熵值: {header_entropy:.2f}")

    if entropy > 7.5:
        print("⚠️ 高熵值！可能被加密或压缩")
    if header_entropy > 6.5:
        print("⚠️ Dex头异常！可能被修改或加固")
