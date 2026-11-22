# k6 summary

scenario: course_visits

- http_req_blocked: med=0.011, max=0.255, p(90)=0.016, p(95)=0.029, p(99)=0.210, avg=0.023, min=0.004
- http_req_tls_handshaking: p(90)=0.000, p(95)=0.000, p(99)=0.000, avg=0.000, min=0.000, med=0.000, max=0.000
- http_req_connecting: p(99)=0.151, avg=0.009, min=0.000, med=0.000, max=0.186, p(90)=0.000, p(95)=0.009
- http_req_receiving: avg=0.330, min=0.050, med=0.329, max=0.757, p(90)=0.512, p(95)=0.674, p(99)=0.740
- http_req_waiting: p(99)=26.746, avg=12.288, min=2.974, med=13.141, max=29.619, p(90)=14.448, p(95)=15.253
- http_req_duration{expected_response:true}: med=13.505, max=30.000, p(90)=14.919, p(95)=15.698, p(99)=27.140, avg=12.669, min=3.068
- http_req_sending: avg=0.050, min=0.011, med=0.043, max=0.195, p(90)=0.055, p(95)=0.067, p(99)=0.170
- http_req_failed: rate=0.000
- vus: min=1.000, max=1.000
- http_req_duration: p(90)=14.919, p(95)=15.698, p(99)=27.140, avg=12.669, min=3.068, med=13.505, max=30.000
- iterations: rate=4.679, count=20.000
