# k6 summary

scenario: teacher_courses

- http_req_tls_handshaking: max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000, avg=0.000, min=0.000, med=0.000
- http_req_duration{expected_response:true}: min=2.617, med=7.452, max=15.157, p(90)=11.674, p(95)=12.445, p(99)=14.999, avg=7.827
- http_req_connecting: p(90)=0.000, p(95)=0.000, p(99)=0.088, avg=0.002, min=0.000, med=0.000, max=0.093
- http_req_blocked: p(90)=0.015, p(95)=0.021, p(99)=0.126, avg=0.012, min=0.001, med=0.011, max=0.133
- vus: min=2.000, max=2.000
- http_req_sending: med=0.037, max=0.091, p(90)=0.052, p(95)=0.054, p(99)=0.072, avg=0.034, min=0.007
- iterations: count=96.000, rate=9.584
- http_req_waiting: avg=7.698, min=2.570, med=7.245, max=14.997, p(90)=11.475, p(95)=12.318, p(99)=14.897
- http_req_receiving: med=0.062, max=0.334, p(90)=0.199, p(95)=0.247, p(99)=0.296, avg=0.094, min=0.020
- http_req_duration: p(90)=11.674, p(95)=12.445, p(99)=14.999, avg=7.827, min=2.617, med=7.452, max=15.157
- http_req_failed: rate=0.000
