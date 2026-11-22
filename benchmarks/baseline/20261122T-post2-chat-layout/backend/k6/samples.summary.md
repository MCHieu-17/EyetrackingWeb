# k6 summary

scenario: samples

- http_req_duration{expected_response:true}: avg=13.612, min=3.339, med=13.314, max=38.602, p(90)=21.396, p(95)=22.615, p(99)=32.313
- iterations: count=236.000, rate=23.186
- http_req_sending: med=0.040, max=0.402, p(90)=0.051, p(95)=0.056, p(99)=0.097, avg=0.040, min=0.005
- http_req_tls_handshaking: min=0.000, med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000, avg=0.000
- http_req_duration: avg=13.612, min=3.339, med=13.314, max=38.602, p(90)=21.396, p(95)=22.615, p(99)=32.313
- http_req_failed: rate=0.000
- http_req_receiving: avg=0.094, min=0.018, med=0.062, max=0.527, p(90)=0.201, p(95)=0.246, p(99)=0.331
- vus: min=5.000, max=5.000
- http_req_blocked: p(99)=0.133, avg=0.013, min=0.002, med=0.011, max=0.135, p(90)=0.014, p(95)=0.023
- http_req_connecting: min=0.000, med=0.000, max=0.100, p(90)=0.000, p(95)=0.000, p(99)=0.098, avg=0.002
- http_req_waiting: p(99)=32.087, avg=13.478, min=3.288, med=13.131, max=38.517, p(90)=21.256, p(95)=22.423
