# k6 summary

scenario: lesson_contents

- http_req_duration{expected_response:true}: min=2.894, med=12.857, max=22.259, p(90)=18.514, p(95)=19.030, p(99)=21.967, avg=12.065
- http_req_tls_handshaking: p(99)=0.000, avg=0.000, min=0.000, med=0.000, max=0.000, p(90)=0.000, p(95)=0.000
- http_req_receiving: min=0.010, med=0.074, max=0.514, p(90)=0.210, p(95)=0.232, p(99)=0.291, avg=0.099
- http_req_connecting: avg=0.002, min=0.000, med=0.000, max=0.097, p(90)=0.000, p(95)=0.000, p(99)=0.093
- vus: min=5.000, max=5.000
- iterations: count=238.000, rate=23.426
- http_req_sending: max=0.150, p(90)=0.050, p(95)=0.057, p(99)=0.077, avg=0.038, min=0.006, med=0.039
- http_req_blocked: med=0.011, max=0.135, p(90)=0.014, p(95)=0.019, p(99)=0.129, avg=0.013, min=0.001
- http_req_duration: med=12.857, max=22.259, p(90)=18.514, p(95)=19.030, p(99)=21.967, avg=12.065, min=2.894
- http_req_failed: rate=0.000
- http_req_waiting: max=22.032, p(90)=18.357, p(95)=18.920, p(99)=21.690, avg=11.927, min=2.844, med=12.622
