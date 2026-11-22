# k6 summary

scenario: teacher_courses

- http_req_sending: p(95)=0.074, p(99)=0.118, avg=0.045, min=0.010, med=0.043, max=0.233, p(90)=0.057
- http_req_receiving: p(99)=0.121, avg=0.048, min=0.010, med=0.045, max=0.131, p(90)=0.065, p(95)=0.077
- vus: min=2.000, max=2.000
- http_req_blocked: avg=0.015, min=0.002, med=0.012, max=0.147, p(90)=0.014, p(95)=0.027, p(99)=0.146
- iterations: count=86.000, rate=8.432
- http_req_duration: avg=36.237, min=20.115, med=38.663, max=78.094, p(90)=45.061, p(95)=48.813, p(99)=78.090
- http_req_connecting: max=0.107, p(90)=0.000, p(95)=0.000, p(99)=0.105, avg=0.002, min=0.000, med=0.000
- http_req_duration{expected_response:true}: p(99)=78.090, avg=36.237, min=20.115, med=38.663, max=78.094, p(90)=45.061, p(95)=48.813
- http_req_failed: rate=0.000
- http_req_waiting: p(90)=44.974, p(95)=48.744, p(99)=77.993, avg=36.144, min=20.063, med=38.545, max=77.999
- http_req_tls_handshaking: med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000, avg=0.000, min=0.000
