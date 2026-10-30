import io,json,sys
from werkzeug.sansio.multipart import MultipartDecoder,File,Field,Data,NeedData,Epilogue
from werkzeug.wrappers import Request

def parse(boundary,body,size):
 decoder=MultipartDecoder(boundary);parts=[]
 for chunk in [*[body[i:i+size] for i in range(0,len(body),size)],None]:
  decoder.receive_data(chunk)
  for _ in range(64):
   event=decoder.next_event()
   if isinstance(event,NeedData):break
   if isinstance(event,(File,Field)):parts.append([event.name,getattr(event,'filename',None),bytearray()])
   if isinstance(event,Data):parts[-1][2].extend(event.data)
   if isinstance(event,Epilogue):return [(n,f,bytes(d)) for n,f,d in parts]
  else:raise RuntimeError('progress')
 raise RuntimeError('incomplete')

checks=0
for boundary in (b'b',b'a.+?b',b'abcabc'):
 for padding in (b'',b' ',b'\t',b' \t \t',b' '*100):
  for ending in (b'\r\n',b''):
   payload=b'\r\n\0\xff\r\n--'+boundary+b'--X\r\n--'+boundary+b'---\r\n--'+boundary+b' '+b'X\r\nend\r'
   body=b'--'+boundary+padding+b'\r\nContent-Disposition: form-data; name="f"; filename="x"\r\n\r\n'+payload+b'\r\n--'+boundary+b'--'+padding+ending
   for size in (1,2,3,7,10000):
    assert parse(boundary,body,size)==[('f','x',payload)],(boundary,padding,ending,size)
    checks+=1
for trailing in (b'\r',b'\r\r',b'\r\n',b'\n\r',b'\r\n\r\n'):
 payload=b'\0'*65535+trailing
 with Request.from_values(data={'upload':(io.BytesIO(payload),'x')},method='POST') as req:assert req.files['upload'].read()==payload
 checks+=1
print(json.dumps({'reference_probe_checks':checks,'passed':checks}))
