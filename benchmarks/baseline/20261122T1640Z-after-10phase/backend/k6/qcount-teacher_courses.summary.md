# k6 summary

scenario: teacher_courses

- http_req_tls_handshaking: avg=0.000, min=0.000, med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000
- http_req_duration{expected_response:true}: min=2.656, med=7.422, max=37.720, p(90)=12.370, p(95)=13.776, p(99)=32.932, avg=9.136
- http_req_waiting: avg=9.010, min=2.608, med=7.313, max=37.600, p(90)=12.145, p(95)=13.512, p(99)=32.783
- iterations: count=20.000, rate=4.760
- http_req_sending: p(90)=0.051, p(95)=0.053, p(99)=0.053, avg=0.037, min=0.012, med=0.041, max=0.053
- http_req_failed: rate=0.000
- vus: min=1.000, max=1.000
- http_req_connecting: avg=0.005, min=0.000, med=0.000, max=0.096, p(90)=0.000, p(95)=0.005, p(99)=0.078
- http_req_duration: avg=9.136, min=2.656, med=7.422, max=37.720, p(90)=12.370, p(95)=13.776, p(99)=32.932
- http_req_blocked: med=0.011, max=0.131, p(90)=0.012, p(95)=0.019, p(99)=0.109, avg=0.016, min=0.003
- http_req_receiving: min=0.025, med=0.066, max=0.231, p(90)=0.172, p(95)=0.185, p(99)=0.222, avg=0.089
