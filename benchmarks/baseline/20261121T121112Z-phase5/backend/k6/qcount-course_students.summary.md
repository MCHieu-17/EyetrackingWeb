# k6 summary

scenario: course_students

- vus: min=1.000, max=1.000
- http_req_duration: p(90)=87.511, p(95)=102.213, p(99)=106.493, avg=68.155, min=37.129, med=64.370, max=107.563
- http_req_receiving: min=0.092, med=0.175, max=0.437, p(90)=0.349, p(95)=0.382, p(99)=0.426, avg=0.221
- http_req_failed: rate=0.000
- http_req_connecting: p(99)=0.058, avg=0.004, min=0.000, med=0.000, max=0.072, p(90)=0.000, p(95)=0.004
- http_req_sending: p(99)=0.096, avg=0.045, min=0.011, med=0.043, max=0.107, p(90)=0.048, p(95)=0.052
- http_req_duration{expected_response:true}: med=64.370, max=107.563, p(90)=87.511, p(95)=102.213, p(99)=106.493, avg=68.155, min=37.129
- iterations: count=20.000, rate=3.715
- http_req_waiting: med=64.170, max=107.019, p(90)=87.118, p(95)=102.059, p(99)=106.027, avg=67.889, min=36.751
- http_req_blocked: med=0.012, max=0.105, p(90)=0.013, p(95)=0.018, p(99)=0.087, avg=0.016, min=0.005
- http_req_tls_handshaking: min=0.000, med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000, avg=0.000
