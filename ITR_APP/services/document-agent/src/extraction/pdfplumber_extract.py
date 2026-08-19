import io,json,sys
import pdfplumber

def main():
    data=sys.stdin.buffer.read()
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        pages=[]
        for number,page in enumerate(pdf.pages,1):
            pages.append({"page":number,"text":page.extract_text() or ""})
    print(json.dumps({"pages":pages,"text":"\n\n".join(p["text"] for p in pages)},ensure_ascii=False))

if __name__=="__main__": main()
