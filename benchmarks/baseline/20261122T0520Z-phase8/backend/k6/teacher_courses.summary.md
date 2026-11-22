# k6 summary

scenario: teacher_courses

- http_req_duration{expected_response:true}: p(99)=28.190, avg=9.488, min=2.436, med=9.822, max=28.549, p(90)=12.465, p(95)=12.746
- http_req_blocked: avg=0.014, min=0.003, med=0.011, max=0.118, p(90)=0.019, p(95)=0.038, p(99)=0.089
- http_req_receiving: p(95)=0.253, p(99)=0.335, avg=0.129, min=0.011, med=0.122, max=0.374, p(90)=0.228
- vus: min=2.000, max=2.000
- http_req_tls_handshaking: avg=0.000, min=0.000, med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000
- http_req_failed: rate=0.000
- iterations: rate=9.504, count=96.000
- http_req_sending: avg=0.041, min=0.009, med=0.041, max=0.082, p(90)=0.053, p(95)=0.064, p(99)=0.075
- http_req_duration: avg=9.488, min=2.436, med=9.822, max=28.549, p(90)=12.465, p(95)=12.746, p(99)=28.190
- http_req_connecting: max=0.085, p(90)=0.000, p(95)=0.000, p(99)=0.066, avg=0.002, min=0.000, med=0.000
- http_req_waiting: p(95)=12.573, p(99)=28.094, avg=9.318, min=2.373, med=9.639, max=28.447, p(90)=12.282
