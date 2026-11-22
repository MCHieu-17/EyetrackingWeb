# k6 summary

scenario: session_contents

- iterations: count=235.000, rate=23.100
- http_req_waiting: p(99)=34.661, avg=15.448, min=6.402, med=12.760, max=36.130, p(90)=25.396, p(95)=30.497
- http_req_duration{expected_response:true}: p(99)=34.769, avg=15.597, min=6.577, med=12.900, max=36.224, p(90)=25.826, p(95)=30.686
- http_req_tls_handshaking: max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000, avg=0.000, min=0.000, med=0.000
- http_req_failed: rate=0.000
- vus: min=5.000, max=5.000
- http_req_receiving: min=0.024, med=0.072, max=0.678, p(90)=0.241, p(95)=0.328, p(99)=0.481, avg=0.111
- http_req_sending: min=0.004, med=0.039, max=0.923, p(90)=0.051, p(95)=0.055, p(99)=0.076, avg=0.039
- http_req_duration: p(99)=34.769, avg=15.597, min=6.577, med=12.900, max=36.224, p(90)=25.826, p(95)=30.686
- http_req_blocked: med=0.010, max=0.130, p(90)=0.014, p(95)=0.023, p(99)=0.125, avg=0.013, min=0.001
- http_req_connecting: p(90)=0.000, p(95)=0.000, p(99)=0.093, avg=0.002, min=0.000, med=0.000, max=0.099
